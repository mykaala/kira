"""One agent turn: build the prompt, call the model with a deadline, validate, retry once,
then fall back to a safe default. The agent holds no truth; it only sees a view."""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ValidationError

from engine.models import ABSTAIN, ClaimIn
from engine.views import PlayerView
from server.settings import Settings

from . import checks
from .costlog import CostLog, cost_usd
from .llm import LLM, Usage
from .personas import CAST, Persona
from .prompt import NO_ACTION, action_choices, observation, persona_block, shared_block
from .schemas import AgentMove, BeliefState, accuse_schema, action_schema, claim_schema, discussion_schema

Delta = Callable[[str], Awaitable[None]]
Retract = Callable[[], Awaitable[None]]
ClaimJudge = Callable[[ClaimIn], str | None]  # why a claim can't be made, or None

NO_CLAIM_RETRY = "Write a new message that makes no role claim; set `claim` to null."


class ModelUnavailable(Exception):
    """The model API stayed unreachable through every reconnect attempt."""


def _is_connection_error(e: BaseException) -> bool:
    return isinstance(e, ConnectionError) or any(c.__name__ == "APIConnectionError" for c in type(e).__mro__)


def schema_names(view: PlayerView) -> list[str]:
    """Every name a schema may hold: the whole cast plus a human at the table. The schema sits in
    front of the prompt, so it must be the same for every call of a type in a game, or nothing
    after it is cached. Who is actually allowed (alive, not you, no teammate kill...) is
    checked in code instead."""
    cast = [p.name for p in CAST]
    return cast + [p.name for p in view.players if p.name not in cast]


class TurnResult(BaseModel):
    say: str
    action: str
    beliefs: BeliefState
    claim: ClaimIn | None = None
    accuses: str | None = None  # player id
    defaulted: bool = False


class SayExtractor:
    """Pulls the `say` string out of streaming JSON so it can be shown while the rest arrives."""

    def __init__(self):
        self.buf = ""
        self.pos: int | None = None  # index just after the opening quote
        self.done = False
        self.emitted = 0

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        if self.done:
            return ""
        if self.pos is None:
            key = self.buf.find('"say"')
            if key < 0:
                return ""
            quote = self.buf.find('"', self.buf.find(":", key) + 1) if ":" in self.buf[key:] else -1
            if quote < 0:
                return ""
            self.pos = quote + 1
        out, i = [], self.pos
        while i < len(self.buf):
            c = self.buf[i]
            if c == '"':
                self.done = True
                break
            if c == "\\":
                if i + 1 >= len(self.buf):
                    break
                if self.buf[i + 1] == "u":
                    if i + 6 > len(self.buf):
                        break
                    out.append(json.loads(f'"{self.buf[i:i + 6]}"'))
                    i += 6
                    continue
                out.append(json.loads(f'"{self.buf[i:i + 2]}"'))
                i += 2
                continue
            out.append(c)
            i += 1
        self.pos = i
        return "".join(out)


class AgentRunner:
    def __init__(self, llm: LLM, settings: Settings, log: CostLog):
        self.llm, self.settings, self.log = llm, settings, log
        self.tokens: dict[str, int] = {}  # game_id -> tokens spent

    def over_budget(self, game_id: str) -> bool:
        return self.tokens.get(game_id, 0) >= self.settings.game_token_budget

    async def play(
        self,
        *,
        game_id: str,
        view: PlayerView,
        persona: Persona,
        beliefs: BeliefState,
        call_type: str,
        default_action: str,
        on_delta: Delta | None = None,
        on_retract: Retract | None = None,
        claim_roles: list[str] | None = None,
        judge_claim: ClaimJudge | None = None,
        used_up: list[str] | None = None,
    ) -> TurnResult:
        """`claim_roles` and `judge_claim` let a discussion message carry a role claim. A claim
        the engine rejects is retried once with the reason; if it fails again, the message is
        regenerated with no claim. `used_up` lists capped phrases the table has spent: using one
        is retried once, then posted anyway."""
        choices, to_id = action_choices(view)
        model = self.settings.model_for(call_type, view.role)
        effort = self.settings.effort_for(call_type, view.role)
        discussion = call_type == "discussion"
        prefix = [
            {"role": "system", "content": shared_block(view.rules, view.roles_revealed_on_death)},
            {"role": "system", "content": persona_block(persona)},
        ]
        max_tokens = self.settings.max_output_tokens if discussion else self.settings.max_output_tokens_action
        error: str | None = None
        fallback: TurnResult | None = None  # a flagged-but-legal first answer, used if the retry fails
        names = {p.id: p.name for p in view.players}
        # the whole game so far, for the reference check
        said: dict[str, list[str]] = {n: [] for n in names.values()}
        for e in view.events:
            if e.kind == "say":
                said[names[e.actor]].append(e.text)
        claimed: dict[str, set[str]] = {}
        for c in view.claims:
            claimed.setdefault(names[c.actor], set()).add(c.role)
        by_name = {p.name: p.id for p in view.players}
        all_names = schema_names(view)
        accusable = {p.name for p in view.players if p.alive and p.id != view.you}
        claims_on = call_type == "discussion" and bool(claim_roles) and judge_claim is not None
        claim_fails, attempts, attempt = 0, 2, -1

        while (attempt := attempt + 1) < attempts:
            if self.over_budget(game_id):
                break
            claim = claim_schema(claim_roles, all_names) if claims_on else None
            schema = (
                discussion_schema(accuse_schema(all_names), claim)
                if discussion
                else action_schema(all_names + [ABSTAIN])
            )
            messages = prefix + [
                {"role": "user", "content": observation(view, persona, beliefs, call_type, choices, error, used_up)}
            ]
            usage, raw, ttft = Usage(), "", None
            extractor, streamed = SayExtractor(), False
            start = time.perf_counter()
            result: TurnResult | None = None
            ref_flag = timed_out = accuse_mismatch = False
            flag_reason: str | None = None
            try:
                # a dropped connection is waited out (it isn't the model's fault), then the game stops
                for wait in [*self.settings.connect_backoff_s, None]:
                    try:
                        async with asyncio.timeout(self.settings.call_timeout_s):
                            async for chunk in self.llm.stream(
                                model=model,
                                messages=messages,
                                schema=schema,
                                max_tokens=max_tokens,
                                reasoning_effort=effort,
                                usage=usage,
                            ):
                                ttft = ttft or time.perf_counter() - start
                                raw += chunk
                                if on_delta and call_type == "discussion" and (d := extractor.feed(chunk)):
                                    streamed = True
                                    await on_delta(d)
                        break
                    except Exception as e:
                        if raw or not _is_connection_error(e):
                            raise
                        if wait is None:
                            raise ModelUnavailable(f"can't reach the model API: {e}") from e
                        await asyncio.sleep(wait)
                        start = time.perf_counter()
                move = AgentMove.model_validate_json(raw)
                say, error = checks.check_say(move.say) if discussion else ("", None)
                if discussion:
                    move.action = NO_ACTION
                if not error and move.action not in to_id:
                    error = f"'{move.action}' is not a legal choice right now; choose one of {choices}"
                if not error and move.accuses and move.accuses not in accusable:
                    if attempt == 0:
                        error = (
                            f"you can't accuse {move.accuses} now: accuse a living player other than yourself "
                            f"({', '.join(sorted(accusable))}) or null"
                        )
                    else:  # keep the message, drop the bad accusation
                        move.accuses = None
                if not error and claims_on and move.claim and move.claim.target and move.claim.target not in by_name:
                    error = f"{move.claim.target} isn't at this table"
                claim_in = None
                if not error and claims_on and move.claim:
                    claim_in = ClaimIn(
                        role=move.claim.role, target=by_name.get(move.claim.target or ""), result=move.claim.result
                    )
                    if why := judge_claim(claim_in):
                        claim_fails += 1
                        error = f"your claim was rejected: {why}. Rewrite the message to match."
                        if claim_fails == 2:  # one more go, with claims switched off
                            claims_on, attempts = False, 3
                            error = f"your claim was rejected: {why}. {NO_CLAIM_RETRY}"
                if not error:
                    accused = by_name.get(move.accuses or "") if discussion else None
                    # logged, not retried: the chip shows the field even if the text names someone else
                    accuse_mismatch = bool(accused and not checks.names(say, move.accuses))
                    # votes and night moves carry no notes; the ones from the last discussion turn stand
                    result = TurnResult(
                        say=say,
                        action=to_id[move.action],
                        beliefs=move.state.trimmed() if discussion else beliefs,
                        claim=claim_in,
                        accuses=accused,
                    )
                    spent = sorted(set(checks.capped_uses(say)) & set(used_up or []))
                    flagged = say and checks.unsupported_references(say, persona.name, said, claimed)
                    if flagged:
                        ref_flag = True
                        flag_reason = checks.flag_reason(flagged)
                    problems = ([checks.REFERENCE_RETRY] if flagged else []) + (
                        [checks.used_up_retry(spent)] if spent else []
                    )
                    if problems and attempt == 0:  # retry once; a second time it is posted anyway
                        fallback, result, error = result, None, " ".join(problems)
            except ModelUnavailable:
                raise
            except TimeoutError:
                timed_out = True
                error = f"timed out after {self.settings.call_timeout_s}s"
            except ValidationError as e:
                error = f"invalid JSON: {e.errors()[0]['msg']}"
            except Exception as e:  # network or API error: retry, then default
                error = f"{type(e).__name__}: {e}"

            self.tokens[game_id] = self.tokens.get(game_id, 0) + usage.input_tokens + usage.output_tokens
            self.log.call(
                game_id=game_id,
                player=persona.name,
                call_type=call_type,
                model=model,
                attempt=attempt,
                input_tokens=usage.input_tokens,
                cached_tokens=usage.cached_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                cost_usd=cost_usd(
                    self.settings.prices, model, usage.input_tokens, usage.cached_tokens, usage.output_tokens
                ),
                ttft_ms=ttft * 1000 if ttft else None,
                latency_ms=(time.perf_counter() - start) * 1000,
                valid=int(result is not None),
                error=None if result else error,
                ref_flag=int(ref_flag),
                flag_reason=flag_reason,
                timed_out=int(timed_out),
                accuse_mismatch=int(accuse_mismatch),
                prompt=json.dumps(messages),
                response=raw,
            )
            if result:
                return result
            if streamed and on_retract:
                await on_retract()

        if fallback:
            return fallback
        return TurnResult(say="", action=default_action, beliefs=beliefs, defaulted=True)
