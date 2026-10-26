"""Generate the giveaway-word lists once, offline: for each location and each cluster, single words and short
phrases that strongly signal it among the game's places. Aliases are added from the location list. The result
goes to src/agents/spy_giveaways.json for review; games read that file and never call this script.
python scripts/spy_giveaways.py"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agents.llm import OpenAILLM, Usage  # noqa: E402
from agents.schemas import _strict  # noqa: E402
from agents.spy_giveaways import PATH  # noqa: E402
from engine.modes.spy_location import CLUSTERS, LOCATION_NAMES, LOCATIONS  # noqa: E402
from server.settings import get_settings  # noqa: E402

SYSTEM = f"""You help build a word filter for a party game. Players are at one secret place from this list:
{", ".join(LOCATION_NAMES)}.
Given a place (or a group of similar places), list words and short phrases (one to three words) that would give it
away: someone who hears the word in an answer could narrow the list down to that place or group. Include objects,
staff, actions, sounds, smells and jargon that belong to it. Leave out generic words that fit many places on the
list (people, line, wait, phone, ticket, crowd, noise, seat, staff, bag, friends, time). Lowercase, singular, no
duplicates, 15 to 30 items. Answer with JSON only: {{"words": [...]}}."""

SCHEMA = _strict("giveaways", {"words": {"type": "array", "items": {"type": "string"}}})


async def ask(llm, s, prompt: str) -> list[str]:
    for _ in range(3):
        raw = ""
        try:
            async for chunk in llm.stream(
                model=s.model_for("judge"),
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                schema=SCHEMA,
                max_tokens=s.max_output_tokens,
                reasoning_effort=s.effort_for("judge"),
                usage=Usage(),
            ):
                raw += chunk
            return json.loads(raw)["words"]
        except Exception as e:  # noqa: BLE001
            print("retry:", type(e).__name__, e, file=sys.stderr)
    raise RuntimeError(f"no answer for: {prompt}")


def clean(words: list[str]) -> list[str]:
    out = []
    for w in words:
        w = " ".join(w.lower().strip(" .,'\"").split())
        if w and len(w.split()) <= 3 and w not in out:
            out.append(w)
    return sorted(out)


async def main() -> None:
    s = get_settings()
    llm = OpenAILLM(s.openai_api_key)
    places = list(LOCATIONS)
    place_words = await asyncio.gather(*(ask(llm, s, f"The place: {p}.") for p in places))
    cluster_words = await asyncio.gather(
        *(
            ask(llm, s, f"The group: {name} ({', '.join(members)}). Words that signal the group as a whole.")
            for name, members in CLUSTERS.items()
        )
    )
    data = {
        "_about": "Giveaway words per place and per cluster, generated once by scripts/spy_giveaways.py "
        "(model: " + s.model_for("judge") + "). Edit by hand freely; games only read this file.",
        "places": {p: clean([p, *LOCATIONS[p], *w]) for p, w in zip(places, place_words)},
        "clusters": {c: clean(w) for c, w in zip(CLUSTERS, cluster_words)},
    }
    PATH.write_text(json.dumps(data, indent=1) + "\n")
    n = sum(map(len, data["places"].values())) + sum(map(len, data["clusters"].values()))
    print(f"wrote {n} words to {PATH}")


if __name__ == "__main__":
    asyncio.run(main())
