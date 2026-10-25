"""One hidden-location turn: build the prompt, call the model with a deadline, check the move in code,
retry once with the reason, then fall back to a default. Same contract as Mafia's runner (whose
streaming block is copied here, so runner.py stays as it is); the moves and checks are this mode's."""

import asyncio
import json
import time
from typing import Any

from pydantic import BaseModel

from engine.modes.spy_location import GUESS, LOCATION_NAMES, names_location
from engine.views import PlayerView
from server.settings import Settings

from . import checks
from .costlog import CostLog, cost_usd
from .llm import LLM, Usage
from .personas import Persona
from .prompt import persona_block
from .runner import ModelUnavailable, _is_connection_error, schema_names
from .spy_prompt import choices, known_location, observation, shared_block
from .spy_schemas import answer_schema, ask_schema, spy_guess_schema, vote_schema

LEAK_RETRY = "you named the location (or a word that is basically its name). Never say it; hint around it instead."
SHORT = {"vote", "spy_guess", "last_chance"}  # one enum field: the small output budget


class SpyTurn(BaseModel):
    move: dict[str, Any] | None = None  # {"target", "text"} | {"text"} | {"target"} | {"location"}
    defaulted: bool = False
    leaked_first: bool = False  # the first attempt named the location (a civilian's ask or answer)


class SpyRunner:
    def __init__(self, llm: LLM, settings: Settings, log: CostLog):
        self.llm, self.settings, self.log = llm, settings, log

    def schema(self, call_type: str, view: PlayerView) -> dict:
        names = schema_names(view)
        return {
            "ask": lambda: ask_schema(names),
            "answer": answer_schema,
            "vote": lambda: vote_schema(names),
            "spy_guess": spy_guess_schema,
            "last_chance": spy_guess_schema,
        }[call_type]()

    def check(self, call_type: str, view: PlayerView, out: dict) -> tuple[dict | None, str | None, bool]:
        """(the move with ids, or None; the error to retry with; whether it names the location)."""
        by_name = {p.name: p.id for p in view.players}
        legal = choices(view, call_type)
        if call_type in ("ask", "vote") and out.get("target") not in legal:
            return None, f"'{out.get('target')}' is not a legal target right now; choose one of {legal}", False
        if call_type in ("spy_guess", "last_chance"):
            loc = out.get("location")
            if loc is None and call_type == "spy_guess":
                return {"location": None}, None, False
            if loc not in legal:
                return None, f"'{loc}' is not a legal location; choose one of the listed locations", False
            return {"location": loc}, None, False
        if call_type == "vote":
            return {"target": by_name[out["target"]]}, None, False
        text, error = checks.check_say(out.get("question" if call_type == "ask" else "text", ""))
        if error:
            return None, error.replace("`say`", "your message"), False
        loc = known_location(view)
        leaked = bool(loc and names_location(text, loc))
        move = {"text": text} | ({"target": by_name[out["target"]]} if call_type == "ask" else {})
        return move, None, leaked

    async def play(self, *, game_id: str, view: PlayerView, persona: Persona, call_type: str) -> SpyTurn:
        model = self.settings.model_for(call_type)
        schema = self.schema(call_type, view)
        prefix = [
            {"role": "system", "content": shared_block()},
            {"role": "system", "content": persona_block(persona)},
        ]
        max_tokens = self.settings.max_output_tokens_action if call_type in SHORT else self.settings.max_output_tokens
        error: str | None = None
        fallback: dict | None = None  # a legal first answer that named the location, if the retry fails
        leaked_first = False
        for attempt in range(2):
            messages = prefix + [{"role": "user", "content": observation(view, persona, call_type, error)}]
            usage, raw, ttft = Usage(), "", None
            start = time.perf_counter()
            move: dict | None = None
            leaked = timed_out = False
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
                move, error, leaked = self.check(call_type, view, json.loads(raw))
                if leaked and attempt == 0:
                    leaked_first = True
                    fallback, move, error = move, None, LEAK_RETRY
            except ModelUnavailable:
                raise
            except TimeoutError:
                timed_out = True
                error = f"timed out after {self.settings.call_timeout_s}s"
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
                ref_flag=int(leaked),
                flag_reason="names the location" if leaked else None,
                timed_out=int(timed_out),
                prompt=json.dumps(messages),
                response=raw,
            )
            if move is not None:
                return SpyTurn(move=move, leaked_first=leaked_first)
        if fallback:
            return SpyTurn(move=fallback, leaked_first=leaked_first)
        return SpyTurn(defaulted=True, leaked_first=leaked_first)


def guess_action(location: str) -> str:
    assert location in LOCATION_NAMES
    return GUESS + location
