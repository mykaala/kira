"""Milestone 1 gate metrics from the cost log: python scripts/report.py [--last 20 | --run runs/x.jsonl] [--db path]
With --run, the games are the ones in that self-play file, and the balance and voice metrics and every
reference-check flag are printed too (older runs are re-scored from their saved transcripts)."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agents.costlog import CostLog  # noqa: E402
from server.runsummary import aggregate, flag_details, format_summary  # noqa: E402
from server.settings import get_settings  # noqa: E402


def p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=20)
    ap.add_argument("--run", help="a runs/*.jsonl file from self-play")
    ap.add_argument("--db", default=str(get_settings().db_path))
    a = ap.parse_args()
    db = sqlite3.connect(a.db)

    summaries = []
    if a.run:
        summaries = [s for line in open(a.run) if (s := json.loads(line))["type"] == "game"]
        if summaries and summaries[0].get("mode") == "spy_location":  # the hidden-location game's own report
            from server.spy_summary import aggregate as spy_aggregate, format_aggregate

            print(format_aggregate(spy_aggregate(CostLog(Path(a.db)), summaries)))
            return
        ids = [s["game_id"] for s in summaries]
        games = db.execute(
            f"SELECT id, started_at, ended_at FROM games WHERE id IN ({','.join('?' * len(ids))})", ids
        ).fetchall()
    else:
        games = db.execute(
            "SELECT id, started_at, ended_at FROM games WHERE winner IS NOT NULL " "ORDER BY started_at DESC LIMIT ?",
            (a.last,),
        ).fetchall()
    if not games:
        print("no finished games in", a.db)
        return
    ids = [g[0] for g in games]
    marks = ",".join("?" * len(ids))
    q = lambda sql: db.execute(sql.format(ids=marks), ids).fetchall()  # noqa: E731

    cost = [r[0] for r in q("SELECT SUM(cost_usd) FROM calls WHERE game_id IN ({ids}) GROUP BY game_id")]
    calls = [r[0] for r in q("SELECT COUNT(*) FROM calls WHERE game_id IN ({ids}) GROUP BY game_id")]
    ttft = [
        r[0]
        for r in q(
            "SELECT ttft_ms FROM calls WHERE game_id IN ({ids}) " "AND call_type='discussion' AND ttft_ms IS NOT NULL"
        )
    ]
    rounds = [r[0] for r in q("SELECT latency_ms FROM rounds WHERE game_id IN ({ids})")]
    turns = q("SELECT COUNT(*) FROM calls WHERE game_id IN ({ids}) AND attempt=0")[0][0]
    failed = q("SELECT COUNT(*) FROM calls WHERE game_id IN ({ids}) AND attempt=1 AND valid=0")[0][0]
    retried = q("SELECT COUNT(*) FROM calls WHERE game_id IN ({ids}) AND attempt=1")[0][0]
    first_try = q("SELECT COUNT(*) FROM calls WHERE game_id IN ({ids}) AND attempt=0 AND valid=0 AND timed_out=0")[0][0]
    minutes = [(g[2] - g[1]) / 60 for g in games if g[2]]
    tokens = q("SELECT SUM(input_tokens), SUM(cached_tokens), SUM(output_tokens) FROM calls WHERE game_id IN ({ids})")[
        0
    ]
    errors = q(
        "SELECT error, COUNT(*) FROM calls WHERE game_id IN ({ids}) AND error IS NOT NULL "
        "GROUP BY error ORDER BY 2 DESC LIMIT 5"
    )

    avg = lambda xs: sum(xs) / len(xs) if xs else 0  # noqa: E731
    fmt = lambda v, unit="": "n/a" if v is None else f"{v:,.2f}{unit}"  # noqa: E731
    invalid = failed / turns if turns else 0
    rows = [
        (
            "Time to first streamed token (p95)",
            fmt((p95(ttft) or 0) / 1000, " s") if ttft else "n/a",
            "< 2 s",
            ttft and p95(ttft) < 2000,
        ),
        (
            "Vote / night round, all AI in (p95)",
            fmt((p95(rounds) or 0) / 1000, " s") if rounds else "n/a",
            "< 4 s",
            rounds and p95(rounds) < 4000,
        ),
        ("Invalid after retry", f"{invalid:.1%} ({failed} of {turns} turns)", "< 1%", invalid < 0.01),
        ("Game length (avg)", fmt(avg(minutes), " min"), "8-12 min", 8 <= avg(minutes) <= 12),
        ("Cost per game (avg / max)", f"${avg(cost):.4f} / ${max(cost):.4f}", "<= $0.15", max(cost) <= 0.15),
    ]
    print(f"\n{len(games)} finished games from {a.db}\n")
    for name, value, target, ok in rows:
        print(f"  {'PASS' if ok else 'MISS'}  {name:<38} {value:<22} target {target}")
    print(
        f"\n  calls per game (avg): {avg(calls):.1f}   turns: {turns}   first-try rejections: {first_try}   "
        f"retried calls: {retried}"
    )
    print(f"  tokens: {tokens[0]:,} in ({tokens[1]:,} cached), {tokens[2]:,} out")
    if errors:
        print("  top errors:")
        for err, n in errors:
            print(f"    {n:>4}  {err[:100]}")

    if summaries:
        log = CostLog(Path(a.db))
        print("\n" + format_summary(aggregate(log, get_settings(), summaries)))
        flags = flag_details(log, ids)
        print(f"\n  reference-check flags ({len(flags)}):")
        for f in flags:
            print(f"    {f['player']} (attempt {f['attempt']}): {f['say']!r}\n      -> {f['reason']}")


if __name__ == "__main__":
    main()
