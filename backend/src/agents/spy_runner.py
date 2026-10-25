"""One hidden-location turn: build the prompt, call the model with a deadline, check the move in code,
retry once with the reason, then fall back to a default. Same contract as Mafia's runner (whose
streaming block is copied here, so runner.py stays as it is); the moves and checks are this mode's."""

import asyncio
import json
import time
from typing import Any

from pydantic import BaseModel

from engine.modes.spy_location import GUESS, LOCATION_NAMES, names_location, names_title
from pathlib import Path
from engine.views import PlayerView
from server.settings import Settings

from . import checks
from .costlog import CostLog, cost_usd
from .llm import LLM, Usage
from .personas import Persona
from .prompt import persona_block
from .runner import ModelUnavailable, _is_connection_error, schema_names
from .spy_giveaways import giveaway
from .spy_guess import MEMO_PATH, GuessMatcher, guess_error, guess_schema
from .spy_prompt import choices, game_options, known_location, observation, own_role, shared_block
from .spy_schemas import answer_schema, ask_schema, vote_schema

LEAK_RETRY = "you named the location (or a word that is basically its name). Never say it; hint around it instead."
TITLE_RETRY = (
    'you said your role\'s title ("{title}"). Never name your role; answer the way that person would, without '
    "saying what they are called."
)
GIVEAWAY_RETRY = (
    "Your answer contains {word}, which gives the place away. "
    "Rewrite it without that, general enough to fit several different places."
)
SHORT = {"vote"}  # one enum field: the small output budget
GUESSES = {"spy_guess", "last_chance"}  # free text plus a little reasoning: the guess budget


class EmptyReply(Exception):
    """A guess call returned no content at all (reasoning can use up the budget): retried, never decisive."""


class SpyTurn(BaseModel):
    move: dict[str, Any] | None = None  # {"target", "text"} | {"text"} | {"target"} | {"guess"}
    defaulted: bool = False
    empty: bool = False  # a guess call came back empty twice: a pass, never a decision
    leaked_first: bool = False  # the first attempt named the location (a civilian's ask or answer)
    giveaway_first: str | None = None  # the giveaway word the first attempt used, if any (civilians only)
    title_first: bool = False  # the first attempt said the civilian's own role title (roles on)


class SpyRunner:
    def __init__(self, llm: LLM, settings: Settings, log: CostLog, memo_path: Path = MEMO_PATH):
        self.llm, self.settings, self.log = llm, settings, log
        self.matcher = GuessMatcher(llm, settings, log, memo_path)

    def schema(self, call_type: str, view: PlayerView) -> dict:
        names = schema_names(view)
        return {
            "ask": lambda: ask_schema(names),
            "answer": answer_schema,
            "vote": lambda: vote_schema(names),
            "spy_guess": guess_schema,
            "last_chance": guess_schema,
        }[call_type]()

    def check(self, call_type: str, view: PlayerView, out: dict) -> tuple[dict | None, str | None, str | None]:
        """(the move with ids, or None; the error to retry with; a flag: "leak" if it names the location,
        "title" if it says the civilian's own role title, "giveaway:<word>" if it uses a giveaway word for the
        place or its cluster, else None)."""
        by_name = {p.name: p.id for p in view.players}
        legal = choices(view, call_type)
        if call_type in ("ask", "vote") and out.get("target") not in legal:
            return None, f"'{out.get('target')}' is not a legal target right now; choose one of {legal}", None
        if call_type in GUESSES:  # free text: one specific place; which one it is, the server decides later
            guess = out.get("guess")
            if error := guess_error(guess, allow_null=call_type == "spy_guess"):
                return None, error, None
            return {"guess": guess.strip() if guess and guess.strip() else None}, None, None
        if call_type == "vote":
            return {"target": by_name[out["target"]]}, None, None
        text, error = checks.check_say(out.get("question" if call_type == "ask" else "text", ""))
        if error:
            return None, error.replace("`say`", "your message"), None
        loc = known_location(view)
        move = {"text": text} | ({"target": by_name[out["target"]]} if call_type == "ask" else {})
        if loc and names_location(text, loc):
            return move, None, "leak"
        if (mine := own_role(view)) and names_title(text, mine["title"]):
            return move, None, "title"
        if loc and game_options(view)["giveaway_check"] and (word := giveaway(text, loc)):
            return move, None, f"giveaway:{word}"
        return move, None, None

    async def play(self, *, game_id: str, view: PlayerView, persona: Persona, call_type: str) -> SpyTurn:
        model = self.settings.model_for(call_type)
        schema = self.schema(call_type, view)
        prefix = [
            {"role": "system", "content": shared_block(view.rules, bool(game_options(view)["roles"]))},
            {"role": "system", "content": persona_block(persona)},
        ]
        max_tokens = (
            self.settings.max_output_tokens_action
            if call_type in SHORT
            else self.settings.max_output_tokens_guess
            if call_type in GUESSES
            else self.settings.max_output_tokens
        )
        error: str | None = None
        fallback: dict | None = None  # a legal first answer that was flagged, if the retry fails
        leaked_first, giveaway_first, title_first = False, None, False

        def firsts() -> dict:
            return {"leaked_first": leaked_first, "giveaway_first": giveaway_first, "title_first": title_first}

        for attempt in range(2):
            messages = prefix + [{"role": "user", "content": observation(view, persona, call_type, error)}]
            usage, raw, ttft = Usage(), "", None
            start = time.perf_counter()
            move: dict | None = None
            flag: str | None = None
            timed_out = empty = False
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
                                reasoning_effort=self.settings.effort_for(call_type),
                                usage=usage,
                            ):
                                ttft = ttft or time.perf_counter() - start
                                raw += chunk
                        break
                    except Exception as e:
                        if raw or not _is_connection_error(e):
                            raise
                        if wait is None:
                            raise ModelUnavailable(f"can't reach the model API: {e}") from e
                        await asyncio.sleep(wait)
                        start = time.perf_counter()
                if call_type in GUESSES and not raw.strip():
                    raise EmptyReply
                move, error, flag = self.check(call_type, view, json.loads(raw))
                if flag and attempt == 0:  # retry once; a second time it is posted anyway
                    if flag == "leak":
                        leaked_first, retry = True, LEAK_RETRY
                    elif flag == "title":
                        title_first, retry = True, TITLE_RETRY.format(title=own_role(view)["title"])
                    else:
                        giveaway_first = flag.removeprefix("giveaway:")
                        retry = GIVEAWAY_RETRY.format(word=giveaway_first)
                    fallback, move, error = move, None, retry
            except ModelUnavailable:
                raise
            except TimeoutError:
                timed_out = True
                error = f"timed out after {self.settings.call_timeout_s}s"
            except EmptyReply:
                empty = True
                error = "empty reply"
            except (ValueError, KeyError, TypeError) as e:
                error = f"invalid JSON: {e}"
            except Exception as e:  # network or API error: retry, then default
                error = f"{type(e).__name__}: {e}"

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
                valid=int(move is not None),
                error=None if move is not None else error,
                ref_flag=int(bool(flag)),
                flag_reason=flag and {"leak": "names the location", "title": "says its role title"}.get(flag, flag),
                timed_out=int(timed_out),
                prompt=json.dumps(messages),
                response=raw,
            )
            if move is not None:
                return SpyTurn(move=move, **firsts())
        if empty:  # the last try came back empty: a pass, logged apart from defaults
            return SpyTurn(empty=True, **firsts())
        if fallback:
            return SpyTurn(move=fallback, **firsts())
        return SpyTurn(defaulted=True, **firsts())


def guess_action(location: str) -> str:
    assert location in LOCATION_NAMES
    return GUESS + location
