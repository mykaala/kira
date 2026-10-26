"""Audit the role bank, offline: for each of the 400 role titles, one judge call lists every place among the 40
where a person with that title plausibly works or would be found. Compares the count with the generator's
generic flag (the audit calls a role generic when it fits >= 5 places). Changes nothing in the bank; writes
docs/spy-roles-audit.md and docs/spy-roles-audit.json.
python scripts/spy_roles_audit.py [--parallel 16]"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agents.costlog import cost_usd  # noqa: E402
from agents.llm import OpenAILLM, Usage  # noqa: E402
from engine.modes.spy_location import CLUSTER_OF, LOCATION_NAMES  # noqa: E402
from engine.modes.spy_roles import ROLES  # noqa: E402
from server.settings import get_settings  # noqa: E402

OUT_MD, OUT_JSON = ROOT.parent / "docs" / "spy-roles-audit.md", ROOT.parent / "docs" / "spy-roles-audit.json"
GENERIC_AT = 5

SYSTEM = f"""You check role cards for a party game. The game's places are:
{", ".join(LOCATION_NAMES)}.
Given a role title, list every place on that list where a person with that title plausibly works or would
plausibly be found on an ordinary day. Include a place only if the title fits it without stretching. Use the place
names exactly as written. Answer with JSON only."""

SCHEMA = {
    "name": "role_fits",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["places"],
        "properties": {"places": {"type": "array", "items": {"type": "string", "enum": LOCATION_NAMES}}},
    },
}


async def fits(llm, s, title: str, sem, cost: list) -> list[str]:
    async with sem:
        for _ in range(3):
            raw, usage = "", Usage()
            try:
                async for chunk in llm.stream(
                    model=s.model_for("role_audit"),
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Role: {title}"}],
                    schema=SCHEMA,
                    max_tokens=s.max_output_tokens,
                    reasoning_effort=s.reasoning_effort,
                    usage=usage,
                ):
                    raw += chunk
                cost.append(cost_usd(s.prices, s.model_for("role_audit"), usage.input_tokens, usage.cached_tokens,
                                     usage.output_tokens))  # fmt: skip
                return sorted(set(json.loads(raw)["places"]))
            except Exception as e:  # noqa: BLE001
                print("retry:", title, type(e).__name__, e, file=sys.stderr)
    raise RuntimeError(f"no answer for {title}")


async def main(parallel: int) -> None:
    s = get_settings()
    llm, sem, cost = OpenAILLM(s.openai_api_key), asyncio.Semaphore(parallel), []
    titles = sorted({r["title"] for rs in ROLES.values() for r in rs})  # a title at several places: judged once
    got = dict(zip(titles, await asyncio.gather(*(fits(llm, s, t, sem, cost) for t in titles))))
    rows = []
    for place, roles in ROLES.items():
        for r in roles:
            f = got[r["title"]]
            same = [p for p in f if CLUSTER_OF[p] == CLUSTER_OF[place]]
            rows.append({"place": place, "title": r["title"], "generic": r["generic"], "fits": f,
                         "count": len(f), "home_fits": place in f, "cluster_fits": len(same)})  # fmt: skip
    OUT_JSON.write_text(json.dumps({"model": s.model_for("role_audit"), "rows": rows}, indent=1))
    write_md(rows, s.model_for("role_audit"), sum(cost), len(titles))
    print(f"wrote {OUT_MD}; {len(titles)} distinct titles judged, cost ${sum(cost):.3f}")


def write_md(rows: list[dict], model: str, cost: float, judged: int) -> None:
    dist = Counter(r["count"] for r in rows)
    flagged_not = [r for r in rows if r["generic"] and r["count"] < GENERIC_AT]
    not_flagged = [r for r in rows if not r["generic"] and r["count"] >= GENERIC_AT]
    only_one = [r for r in rows if r["count"] == 1]
    missing_home = [r for r in rows if not r["home_fits"]]
    fmt = lambda r: f"| {r['place']} | {r['title']} | {r['count']} | {', '.join(r['fits']) or '(none)'} |"  # noqa: E731
    head = ["| Place | Title | Fits | Places it fits |", "|---|---|---|---|"]
    lines = [
        "# Out of Place: role audit",
        "",
        f"One judge call per distinct role title ({judged} titles for {len(rows)} roles; model {model}, "
        f"${cost:.3f}). The judge saw only the title and the 40-place list, and listed every place where a person "
        f"with that title plausibly works or would be found. The audit calls a role generic when it fits "
        f">= {GENERIC_AT} places. Nothing in the bank was changed.",
        "",
        "## How many places each role fits",
        "",
        "| Places | Roles |",
        "|---|---|",
        *[f"| {k} | {dist[k]} |" for k in sorted(dist)],
        "",
        f"Mean {sum(r['count'] for r in rows) / len(rows):.1f}; generic-flagged roles mean "
        f"{_mean([r['count'] for r in rows if r['generic']])}, the rest {_mean([r['count'] for r in rows if not r['generic']])}.",
        "",
        f"## Roles that fit only one place ({len(only_one)})",
        "",
        *head,
        *map(fmt, only_one),
        "",
        f"## Flagged generic by the generator, but fit fewer than {GENERIC_AT} places ({len(flagged_not)})",
        "",
        *head,
        *map(fmt, flagged_not),
        "",
        f"## Not flagged generic, but fit {GENERIC_AT} or more places ({len(not_flagged)})",
        "",
        *head,
        *map(fmt, not_flagged),
        "",
        f"## The judge didn't list the role's own place ({len(missing_home)})",
        "",
        *head,
        *map(fmt, missing_home),
        "",
        "## Per place",
        "",
        "| Place | Generic (bank) | Generic (audit, >= 5) | Fit only here |",
        "|---|---|---|---|",
    ]
    for place in LOCATION_NAMES:
        rs = [r for r in rows if r["place"] == place]
        lines.append(f"| {place} | {sum(r['generic'] for r in rs)} | {sum(r['count'] >= GENERIC_AT for r in rs)} | "
                     f"{sum(r['count'] == 1 and r['home_fits'] for r in rs)} |")  # fmt: skip
    OUT_MD.write_text("\n".join(lines) + "\n")


def _mean(xs: list[int]) -> str:
    return f"{sum(xs) / len(xs):.1f}" if xs else "n/a"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--parallel", type=int, default=16)
    asyncio.run(main(ap.parse_args().parallel))
