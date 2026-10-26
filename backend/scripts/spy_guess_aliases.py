"""Generate the guess-matching aliases once, offline: for each location, 5-10 other names or clear synonyms for
exactly that place. Then check them: an alias that two places share, that equals another place's name, or that is
only part of its own place's name ("airport" for airport lounge) is dropped and reported. The result goes to
src/agents/spy_guess_aliases.json for review; games read that file and never call this script.
python scripts/spy_guess_aliases.py"""

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agents.llm import OpenAILLM, Usage  # noqa: E402
from agents.schemas import _strict  # noqa: E402
from agents.spy_guess import ALIASES_PATH, is_subphrase, normalize  # noqa: E402
from engine.modes.spy_location import LOCATION_NAMES  # noqa: E402
from server.settings import get_settings  # noqa: E402

SYSTEM = """You list other names for a place. Give 5 to 10 other names or clear synonyms that people use for exactly
this kind of place: the same place under another name (for "vet clinic": veterinary clinic, animal hospital, vet's
office). No broader categories, no related or nearby places, no parts of the place, no brand names. Lowercase, a
few words each. Answer with JSON only: {"aliases": [...]}."""
SCHEMA = _strict("aliases", {"aliases": {"type": "array", "items": {"type": "string"}}})


async def ask(llm, s, place: str) -> list[str]:
    for _ in range(3):
        raw = ""
        try:
            async for chunk in llm.stream(
                model=s.model_for("judge"),
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"The place: {place}."}],
                schema=SCHEMA,
                max_tokens=s.max_output_tokens,
                reasoning_effort=s.effort_for("judge"),
                usage=Usage(),
            ):
                raw += chunk
            return json.loads(raw)["aliases"]
        except Exception as e:  # noqa: BLE001
            print("retry:", type(e).__name__, e, file=sys.stderr)
    raise RuntimeError(f"no aliases for {place}")


async def main() -> None:
    s = get_settings()
    llm = OpenAILLM(s.openai_api_key)
    raw = dict(zip(LOCATION_NAMES, await asyncio.gather(*(ask(llm, s, p) for p in LOCATION_NAMES))))
    names = {normalize(p): p for p in LOCATION_NAMES}
    owners: dict[str, set[str]] = defaultdict(set)
    for place, aliases in raw.items():
        for a in aliases:
            owners[normalize(a)].add(place)
    dropped: list[str] = []
    out: dict[str, list[str]] = {}
    for place, aliases in raw.items():
        keep, seen = [], {normalize(place)}
        for a in aliases:
            a = " ".join(a.lower().split()).strip(" .,'\"")
            n = normalize(a)
            if not n or n in seen:
                continue
            why = (
                f"also given for {sorted(owners[n] - {place})}"
                if len(owners[n]) > 1
                else f"is the name of {names[n]}"
                if n in names
                else "only part of the place's name"
                if is_subphrase(n, normalize(place))
                else None
            )
            if why:
                dropped.append(f"{place}: '{a}' {why}")
                continue
            seen.add(n)
            keep.append(a)
        out[place] = keep[:10]
    data = {
        "_about": "Other names for each place, for matching the spy's free-text guess. Generated once by "
        f"scripts/spy_guess_aliases.py (model: {s.model_for('judge')}); no alias belongs to two places. "
        "Edit by hand freely; games only read this file.",
        "aliases": out,
        "dropped": dropped,
    }
    ALIASES_PATH.write_text(json.dumps(data, indent=1) + "\n")
    short = [p for p, a in out.items() if len(a) < 5]
    print(f"wrote {sum(map(len, out.values()))} aliases for {len(out)} places to {ALIASES_PATH}")
    print(f"dropped {len(dropped)}; places with fewer than 5 left: {short or 'none'}")


if __name__ == "__main__":
    asyncio.run(main())
