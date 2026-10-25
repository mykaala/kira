"""Per-game and aggregate run summaries, built from the cost log. Tokens are the API's
reported usage; dollars come from the price table in settings."""

import json
from collections import Counter

from agents.costlog import CostLog, cost_usd
from engine.models import GameState

from .metrics import aggregate_metrics, format_metrics, game_metrics, parse_transcript, record_of
from .settings import Settings

CALL_TYPES = ("discussion", "vote", "night", "summary")


def percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))]


def transcript(state: GameState) -> list[str]:
    """The whole game, secrets included, for reading back a self-play run."""
    names = {p.id: f"{p.name} ({p.role})" for p in state.players}
    lines = []
    for e in state.events:
        if e.kind == "phase":
            lines.append(f"=== {e.text} ===")
        elif e.kind == "say":
            lines.append(f"  {names[e.actor]}: {e.text}")
        else:
            tag = "" if e.vis == "public" else f"[{e.vis}] "
            lines.append(f"  · {tag}{e.text}")
    return lines


def _claim_rejection(row: dict) -> bool:
    return (row["error"] or "").startswith("your claim was rejected")


def _group(rows: list[dict], keys: tuple[str, ...]) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = {}
    for r in rows:
        out.setdefault(tuple(r[k] for k in keys), []).append(r)
    return out


def _call_stats(rows: list[dict], settings: Settings) -> dict:
    by_type = {t: [r for r in rows if r["call_type"] == t] for t in CALL_TYPES}
    return {
        "calls": {"total": len(rows), **{t: len(rs) for t, rs in by_type.items()}},
        "tokens": {
            "input": sum(r["input_tokens"] for r in rows),
            "output": sum(r["output_tokens"] for r in rows),
            "cached_input": sum(r["cached_tokens"] for r in rows),
            "reasoning": sum(r["reasoning_tokens"] or 0 for r in rows),
        },
        "by_model": {
            m: {
                "calls": len(rs),
                "input": sum(r["input_tokens"] for r in rs),
                "cached_input": sum(r["cached_tokens"] for r in rs),
                "output": sum(r["output_tokens"] for r in rs),
                "reasoning": sum(r["reasoning_tokens"] or 0 for r in rs),
                "cost_usd": round(
                    sum(
                        cost_usd(settings.prices, m, r["input_tokens"], r["cached_tokens"], r["output_tokens"])
                        for r in rs
                    ),
                    6,
                ),
            }
            for m in sorted({r["model"] for r in rows})
            for rs in [[r for r in rows if r["model"] == m]]
        },
        # model x role x call type: which role used which model, and what it cost
        "by_model_role": [
            {
                "model": m,
                "role": role,
                "call_type": t,
                "calls": len(rs),
                "input": sum(r["input_tokens"] for r in rs),
                "cached_input": sum(r["cached_tokens"] for r in rs),
                "output": sum(r["output_tokens"] for r in rs),
                "cost_usd": round(
                    sum(
                        cost_usd(settings.prices, m, r["input_tokens"], r["cached_tokens"], r["output_tokens"])
                        for r in rs
                    ),
                    6,
                ),
            }
            for (m, role, t), rs in sorted(_group(rows, ("model", "role", "call_type")).items())
        ],
        "tokens_by_type": {
            t: {
                "input": sum(r["input_tokens"] for r in rs),
                "cached_input": sum(r["cached_tokens"] for r in rs),
                "calls_with_cache_hit": sum(r["cached_tokens"] > 0 for r in rs),
                "output": sum(r["output_tokens"] for r in rs),
                "reasoning": sum(r["reasoning_tokens"] or 0 for r in rs),
                "output_per_call": round(sum(r["output_tokens"] for r in rs) / len(rs), 1),
            }
            for t, rs in by_type.items()
            if rs
        },
        "cost_usd": round(
            sum(
                cost_usd(settings.prices, r["model"], r["input_tokens"], r["cached_tokens"], r["output_tokens"])
                for r in rows
            ),
            6,
        ),
        "latency_ms": {
            t: {
                "p50": percentile([r["latency_ms"] for r in rs], 0.5),
                "p95": percentile([r["latency_ms"] for r in rs], 0.95),
            }
            for t, rs in by_type.items()
            if rs
        },
        # a first answer rejected for any reason (illegal pick, bad JSON, claim, flag, used-up word);
        # each one gets a retry, so this is not the same as an invalid move
        "first_try_rejections": sum(r["attempt"] == 0 and not r["valid"] and not r["timed_out"] for r in rows),
        # answers still unusable after the retry (the turn then falls back to a default move)
        "invalid_after_retry": sum(r["attempt"] == 1 and not r["valid"] and not r["timed_out"] for r in rows)
        - sum(r["attempt"] == 2 and r["valid"] for r in rows),
        "claim_rejections": sum(_claim_rejection(r) for r in rows),
        "accuse_mismatches": sum(bool(r["accuse_mismatch"]) and bool(r["valid"]) for r in rows),
        "retries": sum(r["attempt"] >= 1 for r in rows),
        "timeouts": sum(r["timed_out"] for r in rows),
        "reference_flags": sum(r["ref_flag"] for r in rows),
        # a turn defaults when its last attempt fails; a third attempt follows a failed second one
        "defaulted_turns": sum(r["attempt"] == 1 and not r["valid"] for r in rows)
        - sum(r["attempt"] == 2 and r["valid"] for r in rows),
    }


def _rows(log: CostLog, game_ids: list[str]) -> list[dict]:
    cols = [
        "call_type",
        "model",
        "attempt",
        "input_tokens",
        "cached_tokens",
        "output_tokens",
        "latency_ms",
        "valid",
        "ref_flag",
        "timed_out",
        "reasoning_tokens",
        "error",
        "accuse_mismatch",
    ]
    marks = ",".join("?" * len(game_ids))
    roles = {}  # (game, player name) -> role, from the games table
    for gid, players in log.db.execute(f"SELECT id, players FROM games WHERE id IN ({marks})", game_ids):
        for p in json.loads(players):
            roles[(gid, p["name"])] = p["role"]
    cur = log.db.execute(f"SELECT game_id, player, {', '.join(cols)} FROM calls WHERE game_id IN ({marks})", game_ids)
    return [dict(zip(cols, r[2:]), role=roles.get((r[0], r[1]), "?")) for r in cur]


def flag_details(log: CostLog, game_ids: list[str]) -> list[dict]:
    """Every reference-check flag with the message and the reason."""
    marks = ",".join("?" * len(game_ids))
    cur = log.db.execute(
        f"SELECT game_id, player, attempt, prompt, response, flag_reason FROM calls "
        f"WHERE ref_flag=1 AND game_id IN ({marks}) ORDER BY id",
        game_ids,
    )
    out = []
    for game_id, player, attempt, prompt, response, reason in cur:
        try:
            say = json.loads(response)["say"]
        except (ValueError, KeyError):
            say = response
        if not reason:
            reason = "(logged before flag reasons were recorded)"
        out.append({"game_id": game_id, "player": player, "attempt": attempt, "say": say, "reason": reason})
    return out


def game_summary(log: CostLog, settings: Settings, game_id: str, state: GameState, fake: bool) -> dict:
    record = record_of(state)
    return {
        "type": "game",
        "game_id": game_id,
        "seed": state.seed,
        "winner": state.winner,
        "days": state.day,
        "players": len(state.players),
        "models": {t: settings.model_for(t) for t in ("discussion", "vote", "night")},
        "model_overrides": settings.overrides(),
        "reveal_role_on_death": settings.reveal_role_on_death,
        "fake_llm": fake,
        **_call_stats(_rows(log, [game_id]), settings),
        "reference_flag_details": flag_details(log, [game_id]),
        "metrics": game_metrics(record),
        "record": record,
        "transcript": transcript(state),
    }


def aggregate(log: CostLog, settings: Settings, games: list[dict]) -> dict:
    n = len(games)
    stats = _call_stats(_rows(log, [g["game_id"] for g in games]), settings)
    wins = Counter(g["winner"] for g in games)
    return {
        "type": "aggregate",
        "games": n,
        "win_rate": {side: round(wins[side] / n, 3) for side in ("village", "mafia")},
        "days_distribution": dict(sorted(Counter(g["days"] for g in games).items())),
        "players_distribution": dict(sorted(Counter(g["players"] for g in games).items())),
        "models": games[0]["models"] if games else {},
        "model_overrides": games[0].get("model_overrides", {}) if games else {},
        **stats,
        "balance": aggregate_metrics([metrics_of(g) for g in games]),
        "per_game_avg": {
            "calls": round(stats["calls"]["total"] / n, 1),
            "cost_usd": round(stats["cost_usd"] / n, 6),
            "max_cost_usd": max(g["cost_usd"] for g in games),
            "input_tokens": round(stats["tokens"]["input"] / n),
            "output_tokens": round(stats["tokens"]["output"] / n),
        },
    }


def metrics_of(summary: dict) -> dict:
    """A game's metrics, recomputed so old runs get new metrics. Older summaries have no record,
    so theirs come from the transcript."""
    return game_metrics(summary["record"] if "record" in summary else parse_transcript(summary))


def _ms(v: float | None) -> str:
    return "n/a" if v is None else f"{v / 1000:.2f}s"


def format_summary(s: dict) -> str:
    calls = s["calls"]
    t = s["tokens"]
    lines = []
    if s["type"] == "game":
        lines.append(f"{s['game_id']}: {s['winner']} wins on day {s['days']} ({s['players']} players)")
    else:
        lines.append(f"AGGREGATE over {s['games']} games")
        lines.append(f"  win rate: village {s['win_rate']['village']:.0%}, mafia {s['win_rate']['mafia']:.0%}")
        lines.append("  game length (days): " + ", ".join(f"{d}d x{c}" for d, c in s["days_distribution"].items()))
        pg = s["per_game_avg"]
        lines.append(f"  per game: {pg['calls']} calls, ${pg['cost_usd']:.4f} avg, ${pg['max_cost_usd']:.4f} max")
    lines.append("  calls: " + ", ".join(f"{k} {v}" for k, v in calls.items()))
    lines.append(
        f"  tokens: {t['input']:,} in, {t['output']:,} out, {t['cached_input']:,} cached in"
        f"   cost ${s['cost_usd']:.4f}"
    )
    lines.append(
        "  latency: " + "; ".join(f"{k} p50 {_ms(v['p50'])} p95 {_ms(v['p95'])}" for k, v in s["latency_ms"].items())
    )
    if "first_try_rejections" in s:
        lines.append(
            f"  first-try rejections {s['first_try_rejections']}, invalid after retry {s['invalid_after_retry']}"
        )
    lines.append(
        f"  retries {s['retries']}, timeouts {s['timeouts']}, "
        f"reference flags {s['reference_flags']}, defaulted turns {s['defaulted_turns']}, "
        f"claim rejections {s.get('claim_rejections', 0)}, "
        f"accuse field vs text mismatches {s.get('accuse_mismatches', 0)}"
    )
    if "by_model" in s:
        lines.append(
            "  by model: "
            + "; ".join(
                f"{m} {v['calls']} calls, {v['input']:,} in ({v['cached_input']:,} cached), {v['output']:,} out "
                f"({v['reasoning']:,} reasoning), ${v['cost_usd']:.4f}"
                for m, v in s["by_model"].items()
            )
        )
    if s.get("by_model_role") and s["type"] == "aggregate":
        lines.append("  by model / role / call type:")
        for v in s["by_model_role"]:
            lines.append(
                f"    {v['model']:<14} {v['role']:<10} {v['call_type']:<10} {v['calls']:>5} calls  "
                f"{v['input']:>10,} in ({v['cached_input']:,} cached)  {v['output']:>8,} out  ${v['cost_usd']:.4f}"
            )
    if "tokens_by_type" in s:
        tbt = {k: v for k, v in s["tokens_by_type"].items() if "cached_input" in v}
        if tbt:
            lines.append(
                "  cached input by call type: "
                + ", ".join(
                    f"{k} {v['cached_input']:,} of {v['input']:,} ({v['cached_input'] / max(1, v['input']):.0%}), "
                    f"hit on {v['calls_with_cache_hit']} calls"
                    for k, v in tbt.items()
                )
            )
        lines.append(
            "  output tokens per call: "
            + ", ".join(
                f"{k} {v['output_per_call']} ({v['reasoning']:,} reasoning of {v['output']:,})"
                for k, v in s["tokens_by_type"].items()
            )
        )
    if "balance" in s:
        lines.append(format_metrics(s["balance"]))
    return "\n".join(lines)
