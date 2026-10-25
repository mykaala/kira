"""Offline specificity judge for self-play, never used in a game: for each civilian answer, a model lists
every location on the list the answer (with its question) would fit. Fewer fits is more specific; the
1-5 rating is a fixed bucket of that count, so it means the same thing in every run."""

import asyncio
import json
import time

from engine.modes.spy_location import LOCATION_NAMES
from server.settings import Settings

from .costlog import CostLog, cost_usd
from .llm import LLM, Usage
from .spy_schemas import judge_schema

JUDGE_SYSTEM = f"""You rate answers from a party game. Players are at one secret location from this list:
{", ".join(LOCATION_NAMES)}.
One player asked another a question, and you get the question and the answer. List EVERY location from the list
where that answer would be a natural, believable answer to that question. Judge the answer on its own: don't
guess which location the game used, and don't leave a location out just because another fits better. A vague
answer ("depends on the day") fits almost all of them; a pointed one ("the salt spray gets everywhere") fits
only a few. Answer with JSON only: {{"fits": [locations, exactly as written in the list]}}."""

# fits -> rating: 5 = pins the place down, 1 = fits nearly anywhere
BUCKETS = [(1, 5), (3, 4), (6, 3), (12, 2), (len(LOCATION_NAMES), 1)]


def rating(fits: int) -> int | None:
    """1-5 from how many locations the answer fits; None if it fits none (the judge found it off-list)."""
    return next((r for top, r in BUCKETS if fits <= top), 1) if fits else None


async def judge_answers(llm: LLM, settings: Settings, log: CostLog, items: list[dict], parallel: int = 8) -> list[dict]:
    """Each item is {"game_id", "question", "answer"}; returns {"fits": [...], "rating": 1-5|None} per item,
    or {} where the call failed twice."""
    sem = asyncio.Semaphore(parallel)
    model = settings.model_for("judge")
    schema = judge_schema()

    async def one(item: dict) -> dict:
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"Question: {item['question']}\nAnswer: {item['answer']}"},
        ]
        async with sem:
            for attempt in range(2):
                usage, raw, start, error = Usage(), "", time.perf_counter(), None
                fits: list[str] | None = None
                try:
                    async with asyncio.timeout(settings.call_timeout_s * 2):
                        async for chunk in llm.stream(
                            model=model,
                            messages=messages,
                            schema=schema,
                            max_tokens=settings.max_output_tokens,
                            reasoning_effort=settings.effort_for("judge"),
                            usage=usage,
                        ):
                            raw += chunk
                    fits = sorted({f for f in json.loads(raw)["fits"] if f in LOCATION_NAMES})
                except Exception as e:  # noqa: BLE001 - a failed judgement is retried, then skipped
                    error = f"{type(e).__name__}: {e}"
                log.call(
                    game_id=item["game_id"],
                    player="judge",
                    call_type="judge",
                    model=model,
                    attempt=attempt,
                    input_tokens=usage.input_tokens,
                    cached_tokens=usage.cached_tokens,
                    output_tokens=usage.output_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                    cost_usd=cost_usd(
                        settings.prices, model, usage.input_tokens, usage.cached_tokens, usage.output_tokens
                    ),
                    latency_ms=(time.perf_counter() - start) * 1000,
                    valid=int(fits is not None),
                    error=error,
                    prompt=json.dumps(messages),
                    response=raw,
                )
                if fits is not None:
                    return {"fits": fits, "rating": rating(len(fits))}
        return {}

    return list(await asyncio.gather(*(one(i) for i in items)))


ROLE_JUDGE_SYSTEM = """You check answers from a party game. Each civilian is at a known location and has a secret role
there, described by a card. You get the location, the card, the question the civilian was asked, and their answer.
Decide two things:
- fits_role: would a person with exactly this role plausibly give this answer to this question? Short or casual
  answers count if they are consistent with the role.
- fits_place: would someone at this location plausibly give this answer to this question?
Answer with JSON only."""

ROLE_JUDGE_SCHEMA = {
    "name": "role_judge",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["fits_role", "fits_place"],
        "properties": {"fits_role": {"type": "boolean"}, "fits_place": {"type": "boolean"}},
    },
}


async def judge_roles(llm: LLM, settings: Settings, log: CostLog, items: list[dict], parallel: int = 8) -> list[dict]:
    """Role consistency, offline. Each item is {"game_id", "place", "card" (the whole bank entry, insider tell
    included: the judge may see it, no player ever does), "question", "answer"}; returns {"fits_role",
    "fits_place"} per item, or {} where the call failed twice."""
    sem = asyncio.Semaphore(parallel)
    model = settings.model_for("role_judge")

    async def one(item: dict) -> dict:
        card = item["card"]
        messages = [
            {"role": "system", "content": ROLE_JUDGE_SYSTEM},
            {
                "role": "user",
                "content": f"Location: {item['place']}\nRole: {card['title']}. Wears: {card['wears']}. Does: "
                f"{card['does']}. Deals with: {card['deals_with']}. Insider detail: {card['insider_tell']}\n"
                f"Question: {item['question']}\nAnswer: {item['answer']}",
            },
        ]
        async with sem:
            for attempt in range(2):
                usage, raw, start, error, out = Usage(), "", time.perf_counter(), None, None
                try:
                    async with asyncio.timeout(settings.call_timeout_s * 2):
                        async for chunk in llm.stream(
                            model=model,
                            messages=messages,
                            schema=ROLE_JUDGE_SCHEMA,
                            max_tokens=settings.max_output_tokens,
                            reasoning_effort=settings.effort_for("role_judge"),
                            usage=usage,
                        ):
                            raw += chunk
                    d = json.loads(raw)
                    out = {"fits_role": bool(d["fits_role"]), "fits_place": bool(d["fits_place"])}
                except Exception as e:  # noqa: BLE001 - a failed judgement is retried, then skipped
                    error = f"{type(e).__name__}: {e}"
                log.call(
                    game_id=item["game_id"],
                    player="judge",
                    call_type="role_judge",
                    model=model,
                    attempt=attempt,
                    input_tokens=usage.input_tokens,
                    cached_tokens=usage.cached_tokens,
                    output_tokens=usage.output_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                    cost_usd=cost_usd(
                        settings.prices, model, usage.input_tokens, usage.cached_tokens, usage.output_tokens
                    ),
                    latency_ms=(time.perf_counter() - start) * 1000,
                    valid=int(out is not None),
                    error=error,
                    prompt=json.dumps(messages),
                    response=raw,
                )
                if out is not None:
                    return out
        return {}

    return list(await asyncio.gather(*(one(i) for i in items)))
