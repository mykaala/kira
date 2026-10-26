"""Contrast tests for civilian answers, offline (replaces the yes/no role-consistency judge, which said yes to
everything). For each AI civilian answer in the given runs, one judge call picks which of 4 role cards (its own plus
3 others from the same place, shuffled) best fits the answer, and one picks which of the 4 places in the true
place's group it fits best. Chance is 25% for both. Seeded, so reruns pick the same distractors.
python scripts/spy_contrast.py --run runs/a.jsonl [--run runs/b.jsonl] [--parallel 16]"""

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agents.costlog import cost_usd  # noqa: E402
from agents.llm import OpenAILLM, Usage  # noqa: E402
from engine.modes.spy_location import CLUSTER_OF, CLUSTERS  # noqa: E402
from engine.modes.spy_roles import ROLES  # noqa: E402
from server.settings import get_settings  # noqa: E402

LABELS = ["A", "B", "C", "D"]
ROLE_SYSTEM = """You read one question and one answer from a party game set at a known location. Four people
at that location are described below. Pick the one who most likely gave this answer. Answer with JSON only."""
PLACE_SYSTEM = """You read one question and one answer from a party game. The answer was given by someone at one
of the four places below. Pick the place where this answer fits best. Answer with JSON only."""
SCHEMA = {
    "name": "pick",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["pick"],
        "properties": {"pick": {"type": "string", "enum": LABELS}},
    },
}


def card(r: dict) -> str:
    return f"{r['title']}: wears {r['wears']}; {r['does']}; deals with {r['deals_with']}"


async def ask(llm, s, system: str, user: str, sem, cost: list) -> str | None:
    model = s.model_for("role_judge")
    async with sem:
        for _ in range(2):
            raw, usage = "", Usage()
            try:
                async for chunk in llm.stream(
                    model=model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    schema=SCHEMA,
                    max_tokens=s.max_output_tokens_action,
                    reasoning_effort=s.reasoning_effort,
                    usage=usage,
                ):
                    raw += chunk
                cost.append(cost_usd(s.prices, model, usage.input_tokens, usage.cached_tokens, usage.output_tokens))
                return json.loads(raw)["pick"]
            except Exception as e:  # noqa: BLE001
                print("retry:", type(e).__name__, e, file=sys.stderr)
    return None


async def one(llm, s, g: dict, a: dict, i: int, sem, cost: list) -> dict:
    rng = random.Random(f"{g['game_id']}:{i}:contrast")
    qa = f"Question: {a['question']}\nAnswer: {a['answer']}"
    out = {"run": g["_run"], "place": g["location"], "role": a.get("place_role"), "answer": a["answer"]}
    places = list(CLUSTERS[CLUSTER_OF[g["location"]]])
    rng.shuffle(places)
    pick = await ask(llm, s, PLACE_SYSTEM, "\n".join(f"{x}: {p}" for x, p in zip(LABELS, places)) + "\n\n" + qa, sem,
                     cost)  # fmt: skip
    out["place_right"] = None if pick is None else places[LABELS.index(pick)] == g["location"]
    if a.get("place_role"):
        mine = next(r for r in ROLES[g["location"]] if r["title"] == a["place_role"])
        options = [mine, *rng.sample([r for r in ROLES[g["location"]] if r is not mine], 3)]
        rng.shuffle(options)
        user = f"Location: {g['location']}\n" + "\n".join(f"{x}: {card(r)}" for x, r in zip(LABELS, options))
        pick = await ask(llm, s, ROLE_SYSTEM, user + "\n\n" + qa, sem, cost)
        out["role_right"] = None if pick is None else options[LABELS.index(pick)] is mine
        out["generic"] = mine["generic"]
    return out


async def main(runs: list[str], parallel: int) -> None:
    s = get_settings()
    llm, sem, cost = OpenAILLM(s.openai_api_key), asyncio.Semaphore(parallel), []
    items = []
    for f in runs:
        for g in map(json.loads, open(f)):
            if g["type"] == "game":
                g["_run"] = f
                items += [(g, a, i) for i, a in enumerate(g["answers"]) if a["role"] == "civilian" and a["ai"]]
    res = await asyncio.gather(*(one(llm, s, g, a, i, sem, cost) for g, a, i in items))
    for f in runs:
        rs = [r for r in res if r["run"] == f]
        pl = [r["place_right"] for r in rs if r["place_right"] is not None]
        ro = [r for r in rs if r.get("role_right") is not None]
        gen = [r["role_right"] for r in ro if r["generic"]]
        spec = [r["role_right"] for r in ro if not r["generic"]]
        rate = lambda xs: f"{sum(xs)}/{len(xs)} = {sum(xs) / len(xs):.0%}" if xs else "n/a"  # noqa: E731
        print(f"{f}: place top-1 {rate(pl)}; role top-1 {rate([r['role_right'] for r in ro])} "
              f"(generic roles {rate(gen)}, specific roles {rate(spec)})")  # fmt: skip
    out = ROOT / "runs" / "spy_contrast.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"wrote {out}; {len(res)} answers, cost ${sum(cost):.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--parallel", type=int, default=16)
    a = ap.parse_args()
    asyncio.run(main(a.run, a.parallel))
