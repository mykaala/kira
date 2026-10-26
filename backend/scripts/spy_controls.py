"""Checks on saved hidden-location runs, no new games:
  controls   re-run every saved spy_guess call (a) as it was, (b) with civilian answers removed,
             (c) with the record from a different game; each both as saved (null allowed) and forced
  leakscan   every prompt the spy received: the location (or an alias) anywhere outside the shared
             block, the shared block byte-identical to the code's, and the schemas the same for every seat
  judgesample  N random judged civilian answers, for checking by hand
python scripts/spy_controls.py controls --run runs/a.jsonl --run runs/b.jsonl"""

import argparse
import asyncio
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agents.llm import OpenAILLM, Usage  # noqa: E402
from agents.spy_schemas import answer_schema, ask_schema, spy_guess_schema, vote_schema  # noqa: E402
from engine.modes.spy_location import LOCATION_NAMES, SPY_MODE, names_location  # noqa: E402
from server.settings import get_settings  # noqa: E402

FORCED = "Name the location now: set `location` to your single best guess from the list, never null."


def load(runs: list[str], db: sqlite3.Connection) -> tuple[dict, dict]:
    games = {g["game_id"]: g for f in runs for line in open(f) if (g := json.loads(line))["type"] == "game"}
    roles = {}
    marks = ",".join("?" * len(games))
    for gid, players in db.execute(f"SELECT id, players FROM games WHERE id IN ({marks})", list(games)):
        roles[gid] = {p["name"]: p["role"] for p in json.loads(players)}
    return games, roles


def record_bounds(user: str) -> tuple[int, int]:
    head = next(h for h in ("THE RECORD:\n", "THE RECORD (") if h in user)  # old runs, then the quoted record
    start = user.index("\n", user.index(head)) + 1
    return start, user.index("\n\n", start)


def strip_civilian_answers(user: str, roles: dict[str, str]) -> str:
    a, b = record_bounds(user)
    keep = [
        line
        for line in user[a:b].split("\n")
        if not ((m := re.match(r"^(\w+): ", line)) and roles.get(m[1]) == "civilian")
    ]
    return user[:a] + "\n".join(keep) + user[b:]


def strip_civilian_lines(user: str, roles: dict[str, str]) -> str:
    """Civilian answers and the questions civilians asked: only the spy's own lines and game notes stay."""
    a, b = record_bounds(user)
    keep = [
        line
        for line in strip_civilian_answers(user, roles)[a:].split("\n\n")[0].split("\n")
        if not ((m := re.match(r"^(\w+) asks \w+: ", line)) and roles.get(m[1]) == "civilian")
    ]
    return user[:a] + "\n".join(keep) + user[b:]


def empty_record(user: str) -> str:
    """No information at all: the model's prior over the locations."""
    a, b = record_bounds(user)
    user = user[:a] + "nothing yet" + user[b:]
    return re.sub(r"\n\nYour last line \(don't repeat it\): [^\n]*", "", user)


def swap_record(user: str, donor: str) -> str:
    a, b = record_bounds(user)
    da, db_ = record_bounds(donor)
    return user[:a] + donor[da:db_] + user[b:]


def force(user: str) -> str:
    i = user.index("YOUR TASK: ")
    return user[:i] + "YOUR TASK: " + FORCED


async def controls(a) -> None:
    s = get_settings()
    db = sqlite3.connect(a.db)
    games, roles = load(a.run, db)
    marks = ",".join("?" * len(games))
    rows = db.execute(
        f"SELECT game_id, prompt FROM calls WHERE call_type='spy_guess' AND attempt=0 AND game_id IN ({marks}) "
        "ORDER BY id",
        list(games),
    ).fetchall()
    llm, schema, sem = OpenAILLM(s.openai_api_key), spy_guess_schema(), asyncio.Semaphore(8)
    order = [gid for gid, _ in rows]

    def donor_for(i: int) -> tuple[str, str]:
        loc = games[rows[i][0]]["location"]
        for k in range(1, len(rows)):  # the next saved guess from a game at another location
            gid, prompt = rows[(i + k) % len(rows)]
            if games[gid]["location"] != loc:
                return gid, json.loads(prompt)[-1]["content"]
        raise RuntimeError("no donor")

    async def call(messages: list[dict]) -> str | None:
        async with sem:
            for _ in range(2):
                try:
                    raw = ""
                    async for chunk in llm.stream(
                        model=s.model_for("spy_guess"),
                        messages=messages,
                        schema=schema,
                        max_tokens=s.max_output_tokens_action,
                        reasoning_effort=s.effort_for("spy_guess"),
                        usage=Usage(),
                    ):
                        raw += chunk
                    return json.loads(raw)["location"]
                except Exception as e:  # noqa: BLE001
                    print("retry:", type(e).__name__, e, file=sys.stderr)
            return "ERROR"

    jobs = []
    for i, (gid, prompt) in enumerate(rows):
        msgs = json.loads(prompt)
        user = msgs[-1]["content"]
        donor_gid, donor = donor_for(i)
        variants = {
            "a_full": user,
            "b_no_civilian_answers": strip_civilian_answers(user, roles[gid]),
            "c_other_game": swap_record(user, donor),
            "d_no_civilian_lines": strip_civilian_lines(user, roles[gid]),
            "e_empty_record": empty_record(user),
        }
        for name, u in variants.items():
            if a.only and name not in a.only:
                continue
            for mode, text in (("as_saved", u), ("forced", force(u))):
                jobs.append((i, gid, donor_gid, name, mode, msgs[:-1] + [{"role": "user", "content": text}]))
    results = await asyncio.gather(*(call(m) for *_, m in jobs))
    out = []
    for (i, gid, donor_gid, name, mode, _), guess in zip(jobs, results):
        out.append(
            {
                "i": i,
                "game": gid,
                "variant": name,
                "mode": mode,
                "guess": guess,
                "truth": games[gid]["location"],
                "donor_truth": games[donor_gid]["location"],
            }
        )
    Path(a.out).write_text("\n".join(json.dumps(r) for r in out) + "\n")
    print(
        f"{len(rows)} saved spy_guess prompts from {len(set(order))} games; chance = 1/{len(LOCATION_NAMES)} = {1 / len(LOCATION_NAMES):.1%}"
    )
    for name in ("a_full", "b_no_civilian_answers", "c_other_game", "d_no_civilian_lines", "e_empty_record"):
        for mode in ("as_saved", "forced"):
            rs = [r for r in out if r["variant"] == name and r["mode"] == mode]
            if not rs:
                continue
            named = [r for r in rs if r["guess"] not in (None, "ERROR")]
            right = sum(r["guess"] == r["truth"] for r in rs)
            line = (
                f"  {name:<22} {mode:<8} right {right}/{len(rs)} = {right / len(rs):.0%}   "
                f"named a place {len(named)}/{len(rs)}"
            )
            if name == "c_other_game":
                donor = sum(r["guess"] == r["donor_truth"] for r in rs)
                line += f"   matched the donor game's location {donor}/{len(rs)}"
            print(line)
    print(f"details: {a.out}")


async def freetext(a) -> None:
    """Saved spy_guess and last_chance prompts, rebuilt with no location list anywhere and a free-text `guess`:
    (a) full transcript and (e) empty transcript; spy_guess both as chosen (null allowed) and forced."""
    from agents.costlog import CostLog
    from agents.spy_guess import decide, guess_error, guess_schema
    from agents.spy_prompt import TASKS, shared_block
    from engine.modes.spy_location import configure

    s = get_settings()
    db = sqlite3.connect(a.db)
    games, _ = load(a.run, db)
    opts = next(iter(games.values()))["options"]
    configure(**opts)  # the rules text the saved games were played with, now without the list
    shared = shared_block(SPY_MODE.rules)
    assert not any(loc in shared for loc in LOCATION_NAMES), "a location name is still in the shared block"
    marks = ",".join("?" * len(games))
    rows = db.execute(
        f"SELECT game_id, call_type, prompt FROM calls WHERE call_type IN ('spy_guess', 'last_chance') "
        f"AND attempt=0 AND game_id IN ({marks}) ORDER BY id",
        list(games),
    ).fetchall()
    llm, sem, log = OpenAILLM(s.openai_api_key), asyncio.Semaphore(8), CostLog(Path(a.db))
    forced_task = "Name the location now: set `guess` to your single best guess, one specific place, never null."

    async def one(gid: str, kind: str, cond: str, mode: str, messages: list[dict]) -> dict:
        truth = games[gid]["location"]
        guess, error = None, None
        async with sem:
            for attempt in range(2):
                msgs = (
                    messages
                    if not error
                    else messages[:-1]
                    + [
                        {
                            "role": "user",
                            "content": messages[-1]["content"] + f"\n\nYour previous answer was rejected: {error}",
                        }
                    ]
                )
                raw = ""
                try:
                    async for chunk in llm.stream(
                        model=s.model_for("spy_guess"),
                        messages=msgs,
                        schema=guess_schema(),
                        max_tokens=s.max_output_tokens_action,
                        reasoning_effort=s.effort_for("spy_guess"),
                        usage=Usage(),
                    ):
                        raw += chunk
                    guess = json.loads(raw)["guess"]
                    error = guess_error(guess, allow_null=mode == "chosen")
                except Exception as e:  # noqa: BLE001
                    error = f"invalid JSON: {e}"
                if not error:
                    break
            row = {
                "game": gid,
                "kind": kind,
                "condition": cond,
                "mode": mode,
                "guess": guess,
                "truth": truth,
                "illegal": error,
            }
            if error or not guess:
                return row | {"match": False, "decided_by": "illegal" if error else "null", "reason": error or "null"}
            d = await decide(llm, s, log, game_id=gid, guess=guess, truth=truth)
            return row | {"match": d.match, "decided_by": d.decided_by, "reason": d.reason}

    jobs = []
    for gid, kind, prompt in rows:
        msgs = json.loads(prompt)
        user = msgs[-1]["content"]
        for cond, u in (("a_full", user), ("e_empty", empty_record(user))):
            i = u.index("YOUR TASK: ") + len("YOUR TASK: ")
            for mode in ["chosen", "forced"] if kind == "spy_guess" else ["forced"]:
                task = TASKS[kind] if (kind == "last_chance" or mode == "chosen") else forced_task
                messages = [{"role": "system", "content": shared}, msgs[1], {"role": "user", "content": u[:i] + task}]
                jobs.append(one(gid, kind, cond, mode, messages))
    out = await asyncio.gather(*jobs)
    Path(a.out).write_text("\n".join(json.dumps(r) for r in out) + "\n")
    n = len(LOCATION_NAMES)
    print(
        f"{len(rows)} saved prompts ({sum(r[1] == 'spy_guess' for r in rows)} spy_guess, "
        f"{sum(r[1] == 'last_chance' for r in rows)} last_chance); chance = 1/{n} = {1 / n:.1%}"
    )
    for kind, mode in (("spy_guess", "chosen"), ("spy_guess", "forced"), ("last_chance", "forced")):
        for cond in ("a_full", "e_empty"):
            rs = [r for r in out if r["kind"] == kind and r["mode"] == mode and r["condition"] == cond]
            named = [r for r in rs if r["guess"] and not r["illegal"]]
            right = sum(r["match"] for r in rs)
            print(
                f"  {kind:<11} {mode:<6} {cond:<7} named {len(named)}/{len(rs)}  right {right}/{len(rs)}"
                + (f" ({right}/{len(named)} of those named)" if mode == "chosen" else "")
                + f"  illegal after retry {sum(bool(r['illegal']) for r in rs)}"
            )
    by = lambda k: [r for r in out if r["decided_by"] == k]  # noqa: E731
    print(
        f"  decisions: deterministic {len(by('deterministic'))} (all matches), judge {len(by('judge'))} "
        f"({sum(r['match'] for r in by('judge'))} matches), judge failed {len(by('judge_failed'))}"
    )
    print(f"details: {a.out}")


async def rescore(a) -> None:
    """Every decided guess from a freetext run, re-decided with the current rules (and the judge memo)."""
    from collections import Counter

    from agents.costlog import CostLog
    from agents.spy_guess import GuessMatcher

    s = get_settings()
    rows = [r for line in open(a.src) if (r := json.loads(line))["guess"] and not r["illegal"]]
    m = GuessMatcher(OpenAILLM(s.openai_api_key), s, CostLog(Path(a.db)))
    new = []
    for r in rows:  # one at a time, so a repeated guess hits the memo
        d = await m.decide(game_id=r["game"], guess=r["guess"], truth=r["truth"])
        new.append(
            r
            | {
                "old_match": r["match"],
                "old_decided_by": r["decided_by"],
                "old_reason": r["reason"],
                "match": d.match,
                "rule": d.rule,
                "reason": d.reason,
            }
        )
    Path(a.out).write_text("\n".join(json.dumps(r) for r in new) + "\n")
    print(f"{len(new)} decisions re-scored; rules: {dict(Counter(r['rule'] for r in new))}")
    changed = [r for r in new if r["match"] != r["old_match"]]
    print(f"verdicts changed: {len(changed)}")
    for r in changed:
        print(
            f"  {r['guess']!r} for {r['truth']}: {r['old_match']} ({r['old_decided_by']}) -> {r['match']} ({r['rule']})"
            f"  [{r['kind']}/{r['mode']}/{r['condition']}]"
        )
    print(f"details: {a.out}; memo: {m.memo_path} ({len(m.memo)} verdicts)")


def _server_written(user: str) -> str:
    """The dynamic prompt minus what players wrote: the record, your own last line, the question you were asked."""
    a, b = record_bounds(user)
    text = user[:a] + user[b:]
    text = re.sub(r"\n\nYour last line \(don't repeat it\): [^\n]*", "", text)
    return re.sub(r"YOUR TASK: .* asked you: [^\n]*", "YOUR TASK:", text)


def nolist(a) -> None:
    """With no location list in any prompt: the spy's prompts name no place at all, a civilian's none but their
    own; checked in every part the server writes (players' own words are reported apart)."""
    from agents.spy_guess import guess_aliases
    from agents.spy_schemas import answer_schema, ask_schema, vote_schema
    from agents.spy_guess import guess_schema
    from engine.modes.spy_location import LOCATIONS, names_location

    db = sqlite3.connect(a.db)
    games, roles = load(a.run, db)
    marks = ",".join("?" * len(games))
    rows = db.execute(
        f"SELECT game_id, player, call_type, prompt FROM calls WHERE game_id IN ({marks}) "
        "AND call_type NOT IN ('judge', 'guess_judge', 'role_judge')",
        list(games),
    ).fetchall()
    words = {p: [p, *LOCATIONS[p], *guess_aliases().get(p, [])] for p in LOCATION_NAMES}
    rx = {p: [re.compile(r"\b" + re.escape(w) + r"\b", re.I) for w in ws] for p, ws in words.items()}
    named = lambda text, p: names_location(text, p) or any(r.search(text) for r in rx[p])  # noqa: E731
    hits, record_hits, shared, counts = [], 0, {}, {}
    for gid, player, call_type, prompt in rows:
        msgs = json.loads(prompt)
        shared.setdefault(gid, set()).add(msgs[0]["content"])
        role = roles[gid].get(player)
        counts[role] = counts.get(role, 0) + 1
        own = games[gid]["location"] if role == "civilian" else None
        parts = {
            "shared": msgs[0]["content"],
            "persona": msgs[1]["content"],
            "dynamic": _server_written(msgs[-1]["content"]),
        }
        for part, text in parts.items():
            for p in LOCATION_NAMES:
                if p != own and named(text, p):
                    hits.append((gid, role, call_type, part, p))
        a_, b_ = record_bounds(msgs[-1]["content"])
        record = msgs[-1]["content"][a_:b_]
        record_hits += any(p != own and named(record, p) for p in LOCATION_NAMES)
    print(f"prompts scanned: {sum(counts.values())} {counts}")
    print(f"  games whose shared block differs between calls or seats: {sum(len(v) > 1 for v in shared.values())}")
    print(f"  a place other than a civilian's own, in server-written text: {len(hits)}")
    for h in hits[:15]:
        print("   ", h)
    print(f"  prompts whose record (players' own words) mentions another place: {record_hits}")
    sch = json.dumps([ask_schema(["A", "B"]), answer_schema(), vote_schema(["A", "B"]), guess_schema()])
    print("  schemas holding a place name:", [p for p in LOCATION_NAMES if p in sch] or "none")


def leakscan(a) -> None:
    db = sqlite3.connect(a.db)
    games, roles = load(a.run, db)
    marks = ",".join("?" * len(games))
    rows = db.execute(
        f"SELECT game_id, player, call_type, prompt FROM calls WHERE game_id IN ({marks}) AND call_type != 'judge'",
        list(games),
    ).fetchall()
    counts, hits, shared = {}, [], {}
    for gid, player, call_type, prompt in rows:
        msgs = json.loads(prompt)
        shared.setdefault(gid, set()).add(msgs[0]["content"])  # every seat and call type
        if roles[gid].get(player) != "spy":
            continue
        counts[call_type] = counts.get(call_type, 0) + 1
        loc = games[gid]["location"]
        for k, m in enumerate(msgs[1:], 1):  # persona and dynamic view
            if names_location(m["content"], loc) or loc in m["content"].lower():
                hits.append((gid, call_type, k, loc))
    print(f"spy prompts scanned: {sum(counts.values())} {counts}")
    print(f"  games whose shared block differs between calls or seats: {sum(len(v) > 1 for v in shared.values())}")
    print(f"  location or alias outside the shared block: {len(hits)}")
    for h in hits[:20]:
        print("   ", h)
    # schemas: built from the cast list only, never from a seat's role or the location
    names = ["A", "B"]
    sch = {
        "ask": ask_schema(names),
        "answer": answer_schema(),
        "vote": vote_schema(names),
        "spy_guess": spy_guess_schema(),
    }
    enum = spy_guess_schema()["schema"]["properties"]["location"]["anyOf"][0]["enum"]
    print(
        f"  spy_guess / last_chance schema lists all {len(enum)} locations in the fixed order: {enum == LOCATION_NAMES}"
    )
    print(
        "  schemas hold a location outside that enum:",
        any(loc in json.dumps(v) for k, v in sch.items() if k != "spy_guess" for loc in LOCATION_NAMES),
    )


def judgesample(a) -> None:
    db = sqlite3.connect(a.db)
    games, _ = load(a.run, db)
    items = [(g, x) for g in games.values() for x in g["answers"] if "rating" in x]
    for g, x in random.Random(a.seed).sample(items, a.n):
        print(
            json.dumps(
                {
                    "game": g["game_id"],
                    "location": g["location"],
                    "q": x["question"],
                    "a": x["answer"],
                    "rating": x["rating"],
                    "fits": x["fits"],
                }
            )
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["controls", "leakscan", "judgesample", "freetext", "rescore", "nolist"])
    ap.add_argument("--src", help="rescore: a freetext output file")
    ap.add_argument("--run", action="append", default=[])
    ap.add_argument("--db", default=str(get_settings().db_path))
    ap.add_argument("--out", default="runs/spy-controls.jsonl")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--only", action="append", help="controls: run only these variants")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    {
        "controls": lambda: asyncio.run(controls(a)),
        "leakscan": lambda: leakscan(a),
        "judgesample": lambda: judgesample(a),
        "freetext": lambda: asyncio.run(freetext(a)),
        "rescore": lambda: asyncio.run(rescore(a)),
        "nolist": lambda: nolist(a),
    }[a.cmd]()
