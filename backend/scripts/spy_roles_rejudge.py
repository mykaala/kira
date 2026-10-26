"""Re-judge the audit's generic-flag disagreements (flagged generic by the generator, but the audit found fewer than
5 places): each title 3 more times, sampled (temperature 1), with the audit's prompt and schema; a title counts as
fitting >= 5 places when at least 2 of the 3 say so. Proposes generic = flagged AND fits >= 5 places, with generic
counts per place and promotion candidates where a place would drop below 3. Changes nothing in the bank.
python scripts/spy_roles_rejudge.py"""

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from spy_roles_audit import GENERIC_AT, OUT_JSON, SCHEMA, SYSTEM  # noqa: E402

from engine.modes.spy_location import LOCATION_NAMES  # noqa: E402
from engine.modes.spy_roles import ROLES  # noqa: E402
from server.settings import get_settings  # noqa: E402

MIN_PER_PLACE, TRIES = 3, 3
OUT = ROOT / "runs" / "spy_generic_proposal.json"


async def fits(client, model: str, title: str, sem) -> int | None:
    async with sem:
        for _ in range(3):
            try:
                r = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Role: {title}"}],
                    response_format={"type": "json_schema", "json_schema": SCHEMA},
                    temperature=1,
                    reasoning_effort="low",
                )
                return len(set(json.loads(r.choices[0].message.content)["places"]))
            except Exception as e:  # noqa: BLE001
                print("retry:", title, type(e).__name__, e, file=sys.stderr)
    return None


async def main() -> None:
    from openai import AsyncOpenAI

    s = get_settings()
    audit = json.loads(OUT_JSON.read_text())["rows"]
    count = {(r["place"], r["title"]): r["count"] for r in audit}
    disputed = sorted({r["title"] for r in audit if r["generic"] and r["count"] < GENERIC_AT})
    client, sem = AsyncOpenAI(api_key=s.openai_api_key, max_retries=2), asyncio.Semaphore(12)
    runs = await asyncio.gather(
        *(fits(client, s.model_for("role_audit"), t, sem) for t in disputed for _ in range(TRIES))
    )
    votes = {t: runs[i * TRIES : (i + 1) * TRIES] for i, t in enumerate(disputed)}
    wide = {t: sum((n or 0) >= GENERIC_AT for n in v) >= 2 for t, v in votes.items()}

    def generic(place: str, r: dict) -> bool:
        if not r["generic"]:
            return False
        return wide[r["title"]] if r["title"] in wide else count[(place, r["title"])] >= GENERIC_AT

    per_place = {}
    for place in LOCATION_NAMES:
        now = sum(r["generic"] for r in ROLES[place])
        new = sum(generic(place, r) for r in ROLES[place])
        candidates = sorted(
            ((r["title"], count[(place, r["title"])]) for r in ROLES[place] if not generic(place, r)),
            key=lambda x: -x[1],
        )
        per_place[place] = {"now": now, "proposed": new, "candidates": candidates[:4] if new < MIN_PER_PLACE else []}
    OUT.write_text(json.dumps({"votes": votes, "fits_5_plus": wide, "per_place": per_place}, indent=1))
    print("| Title | 3 re-judgements (places) | Majority >= 5 | Proposed |\n|---|---|---|---|")
    for t, v in votes.items():
        print(
            f"| {t} | {', '.join(map(str, v))} | {'yes' if wide[t] else 'no'} | {'stays generic' if wide[t] else 'not generic'} |"
        )
    print("\n| Place | Generic now | Proposed | Promotion candidates (audit fits) |\n|---|---|---|---|")
    for p, d in per_place.items():
        cands = ", ".join(f"{t} ({n})" for t, n in d["candidates"])
        print(f"| {p} | {d['now']} | {d['proposed']}{' ⚠' if d['proposed'] < MIN_PER_PLACE else ''} | {cands} |")
    print(f"\n{Counter(d['proposed'] for d in per_place.values())}; wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
