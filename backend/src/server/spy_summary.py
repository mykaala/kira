"""Per-game and aggregate summaries for hidden-location self-play: how rounds end, how well each side
plays, and what each call type costs. Built from the game state and the cost log."""

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from agents.costlog import CostLog
from engine.models import GameState
from engine.modes.spy_location import CIVILIAN, SPY, location, names_location

from .runsummary import percentile

CALL_TYPES = ("ask", "answer", "vote", "spy_guess", "last_chance", "judge")
STOP = set(
    "a an the u you your ur do does did is are was were what whats what's how when who whom where why which "
    "would could should will can there here it its it's of to in on at for with and or but if so be like usually "
    "first thing get got go going people most lol ngl tbh ok kinda really".split()
)


def transcript(state: GameState) -> list[str]:
    names = {p.id: f"{p.name} ({p.role})" for p in state.players}
    lines = []
    for e in state.events:
        if e.kind == "phase":
            continue
        if e.kind == "ask":
            lines.append(f"  {names[e.actor]} -> {names[e.target]}: {e.text}")
        elif e.kind == "answer":
            lines.append(f"  {names[e.actor]}: {e.text}")
        else:
            tag = "" if e.vis == "public" else f"[{e.vis}] "
            lines.append(f"  · {tag}{e.text}")
    return lines


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP}


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z']+", text.lower()))


def is_repeat(question: str, earlier: list[str]) -> bool:
    """The same question as an earlier one, word for word or near enough (same content words, or a
    close string match)."""
    w = _words(question)
    for q in earlier:
        if SequenceMatcher(None, _norm(question), _norm(q)).ratio() >= 0.8:
            return True
        if len(w) >= 2 and w == _words(q):
            return True
    return False


def _rows(log: CostLog, game_ids: list[str]) -> list[dict]:
    cols = [
        "call_type",
        "attempt",
        "input_tokens",
        "cached_tokens",
        "output_tokens",
        "cost_usd",
        "latency_ms",
        "valid",
        "ref_flag",
        "timed_out",
    ]
    marks = ",".join("?" * len(game_ids))
    cur = log.db.execute(f"SELECT {', '.join(cols)} FROM calls WHERE game_id IN ({marks})", game_ids)
    return [dict(zip(cols, r)) for r in cur]


def call_stats(rows: list[dict], games: int) -> dict:
    out = {}
    for t in CALL_TYPES:
        rs = [r for r in rows if r["call_type"] == t]
        if not rs:
            continue
        lat = [r["latency_ms"] for r in rs]
        cost = sum(r["cost_usd"] or 0 for r in rs)
        out[t] = {
            "calls": len(rs),
            "turns": sum(r["attempt"] == 0 for r in rs),
            "retries": sum(r["attempt"] >= 1 for r in rs),
            "invalid": sum(not r["valid"] and not r["ref_flag"] for r in rs),
            "timeouts": sum(r["timed_out"] for r in rs),
            "input": sum(r["input_tokens"] for r in rs),
            "cached_input": sum(r["cached_tokens"] for r in rs),
            "output": sum(r["output_tokens"] for r in rs),
            "cost_usd": round(cost, 6),
            "cost_per_game": round(cost / games, 6),
            "cost_per_call": round(cost / len(rs), 7),
            "latency_p50_ms": percentile(lat, 0.5),
            "latency_p95_ms": percentile(lat, 0.95),
        }
    return out


def game_summary(log: CostLog, game, human_seat: str, options: dict) -> dict:
    s: GameState = game.state
    roles = {p.id: p.role for p in s.players}
    names = {p.id: p.name for p in s.players}
    loc = location(s)
    human = {p.id for p in s.players if p.is_human}
    ev = s.events
    kinds = {e.kind for e in ev}
    accused = next((e for e in ev if e.kind == "accused"), None)
    if "guess" in kinds:
        end = "guess_right" if s.winner == SPY else "guess_wrong"
    elif "last_guess" in kinds:
        end = "caught_last_right" if s.winner == SPY else "caught_last_wrong"
    elif accused and accused.target is None:
        end = "tie"
    elif accused and roles[accused.target] == SPY:
        end = "caught"
    else:
        end = "wrong_vote"

    asks = [e for e in ev if e.kind == "ask"]
    questions, answers = [], []
    for i, e in enumerate(asks):
        questions.append(
            {
                "actor": names[e.actor],
                "role": roles[e.actor],
                "ai": e.actor not in human,
                "text": e.text,
                "leak": roles[e.actor] == CIVILIAN and names_location(e.text, loc),
                "repeat": is_repeat(e.text, [q.text for q in asks[:i]]),
            }
        )
    for e in ev:
        if e.kind == "answer":
            q = next(a for a in reversed(asks) if a.seq < e.seq)
            answers.append(
                {
                    "actor": names[e.actor],
                    "role": roles[e.actor],
                    "ai": e.actor not in human,
                    "question": q.text,
                    "asker": names[q.actor],
                    "answer": e.text,
                    "leak": roles[e.actor] == CIVILIAN and names_location(e.text, loc),
                }
            )
    guess = next((e for e in ev if e.kind == "guess"), None)
    last = next((e for e in ev if e.kind == "last_guess"), None)
    votes = [e for e in ev if e.kind == "vote"]
    civ_votes = [v for v in votes if roles[v.actor] == CIVILIAN]
    named = lambda e: e.text.split(": ", 1)[1].removesuffix(".")  # noqa: E731
    return {
        "type": "game",
        "mode": s.mode,
        "game_id": game.id,
        "seed": s.seed,
        "players": len(s.players),
        "human_seat": human_seat,
        "options": options,
        "winner": s.winner,
        "location": loc,
        "spy": next(names[p] for p, r in roles.items() if r == SPY),
        "end": end,
        "exchanges": len(asks),
        "exchange_cap": 2 * len(s.players),
        "guess": guess
        and {
            "exchange": len([a for a in asks if a.seq < guess.seq]),
            "location": named(guess),
            "right": s.winner == SPY,
        },
        "last_chance": last and {"location": named(last), "right": s.winner == SPY},
        "votes": {
            "cast": len(votes),
            "civilian": len(civ_votes),
            "civilian_on_spy": sum(roles[v.target] == SPY for v in civ_votes),
            "accused_spy": bool(accused and accused.target and roles[accused.target] == SPY),
        }
        if votes
        else None,
        "guess_windows": game.guess_windows,
        "defaulted": dict(game.defaulted),
        "leaked_first": dict(game.leaked_first),
        "questions": questions,
        "answers": answers,
        "calls": call_stats(_rows(log, [game.id]), 1),
        "transcript": transcript(s),
    }


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def aggregate(log: CostLog, games: list[dict]) -> dict:
    n = len(games)
    ends = Counter(g["end"] for g in games)
    voted = [g for g in games if g["votes"]]
    guesses = [g for g in games if g["guess"]]
    lasts = [g for g in games if g["last_chance"]]
    by_loc, by_ex = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for g in guesses:
        for key, table in ((g["location"], by_loc), (g["guess"]["exchange"], by_ex)):
            table[key][0] += g["guess"]["right"]
            table[key][1] += 1
    ai_civ_answers = [a for g in games for a in g["answers"] if a["role"] == CIVILIAN and a["ai"]]
    ai_civ_questions = [q for g in games for q in g["questions"] if q["role"] == CIVILIAN and q["ai"]]
    ai_questions = [q for g in games for q in g["questions"] if q["ai"]]
    rated = [a for g in games for a in g["answers"] if a["role"] == CIVILIAN and a.get("rating")]
    judged = [a for g in games for a in g["answers"] if a["role"] == CIVILIAN and "fits" in a]
    true_fit = [
        a for g in games for a in g["answers"] if a["role"] == CIVILIAN and "fits" in a and g["location"] in a["fits"]
    ]
    by_n = defaultdict(lambda: [0, 0])
    for g in games:
        by_n[g["players"]][0] += g["winner"] == SPY
        by_n[g["players"]][1] += 1
    chance = [1 / (g["players"] - 1) for g in voted]
    return {
        "type": "aggregate",
        "mode": games[0]["mode"] if games else None,
        "games": n,
        "options": games[0]["options"] if games else {},
        "human_seat": games[0]["human_seat"] if games else None,
        "spy_win_rate": _rate(sum(g["winner"] == SPY for g in games), n),
        "spy_win_rate_by_players": {k: _rate(*v) for k, v in sorted(by_n.items())},
        "ends": {k: ends[k] for k in sorted(ends)},
        "tie_rate": _rate(ends["tie"], n),
        "vote": {
            "rounds_voted": len(voted),
            "accused_spy": _rate(sum(g["votes"]["accused_spy"] for g in voted), len(voted)),
            "civilian_votes_on_spy": _rate(
                sum(g["votes"]["civilian_on_spy"] for g in voted), sum(g["votes"]["civilian"] for g in voted)
            ),
            "chance": round(sum(chance) / len(chance), 3) if chance else None,
        },
        "spy_guess": {
            "windows": sum(g["guess_windows"] for g in games),
            "guesses": len(guesses),
            "accuracy": _rate(sum(g["guess"]["right"] for g in guesses), len(guesses)),
            "by_location": {k: f"{r}/{t}" for k, (r, t) in sorted(by_loc.items())},
            "by_exchange": {k: f"{r}/{t}" for k, (r, t) in sorted(by_ex.items())},
        },
        "last_chance": {
            "guesses": len(lasts),
            "accuracy": _rate(sum(g["last_chance"]["right"] for g in lasts), len(lasts)),
        },
        "exchanges": {
            "mean": round(sum(g["exchanges"] for g in games) / n, 2) if n else None,
            "distribution": dict(sorted(Counter(g["exchanges"] for g in games).items())),
            "ran_to_cap": _rate(sum(g["exchanges"] == g["exchange_cap"] for g in games), n),
        },
        "specificity": {
            "judged": len(judged),
            "mean": round(sum(a["rating"] for a in rated) / len(rated), 2) if rated else None,
            "share_1_2": _rate(sum(a["rating"] <= 2 for a in rated), len(rated)),
            "distribution": dict(sorted(Counter(a["rating"] for a in rated).items())),
            "fits_none": sum(not a["fits"] for a in judged),
            "fits_true_location": _rate(len(true_fit), len(judged)),
        },
        "leak": {
            "answers": len(ai_civ_answers),
            "answers_raw": _rate(sum(g["leaked_first"].get("answer", 0) for g in games), len(ai_civ_answers)),
            "answers_posted": _rate(sum(a["leak"] for a in ai_civ_answers), len(ai_civ_answers)),
            "questions": len(ai_civ_questions),
            "questions_raw": _rate(sum(g["leaked_first"].get("ask", 0) for g in games), len(ai_civ_questions)),
            "questions_posted": _rate(sum(q["leak"] for q in ai_civ_questions), len(ai_civ_questions)),
        },
        "repeated_questions": {
            "rate": _rate(sum(q["repeat"] for q in ai_questions), len(ai_questions)),
            "count": sum(q["repeat"] for q in ai_questions),
        },
        "defaulted": dict(sum((Counter(g["defaulted"]) for g in games), Counter())),
        "calls": call_stats(_rows(log, [g["game_id"] for g in games]), n),
    }


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.0%}"


def _ms(v: float | None) -> str:
    return "n/a" if v is None else f"{v / 1000:.2f}s"


def format_game(g: dict) -> str:
    how = {
        "guess_right": "spy named it",
        "guess_wrong": "spy misnamed it",
        "caught": "spy voted out",
        "caught_last_right": "spy voted out, then named it",
        "caught_last_wrong": "spy voted out, misnamed it",
        "wrong_vote": "a civilian voted out",
        "tie": "tied vote",
    }[g["end"]]
    cost = sum(c["cost_usd"] for c in g["calls"].values())
    who = "the spy wins" if g["winner"] == SPY else "the civilians win"
    return (
        f"{g['game_id']}: {who} ({how}), {g['players']} players, location {g['location']}, "
        f"spy {g['spy']}, {g['exchanges']}/{g['exchange_cap']} exchanges, ${cost:.4f}"
    )


def format_aggregate(a: dict) -> str:
    v, sg, lc, ex, sp, lk = a["vote"], a["spy_guess"], a["last_chance"], a["exchanges"], a["specificity"], a["leak"]
    lines = [
        f"AGGREGATE over {a['games']} games ({a['mode']}, human seat: {a['human_seat']}, options {a['options']})",
        f"  spy win rate {_pct(a['spy_win_rate'])}; by players: "
        + ", ".join(f"{k}p {_pct(r)}" for k, r in a["spy_win_rate_by_players"].items()),
        "  how rounds ended: "
        + ", ".join(f"{k} {c}" for k, c in a["ends"].items())
        + f"; tie rate {_pct(a['tie_rate'])}",
        f"  vote: accused the spy in {_pct(v['accused_spy'])} of {v['rounds_voted']} votes; civilian votes on the spy "
        f"{_pct(v['civilian_votes_on_spy'])} vs chance {_pct(v['chance'])}",
        f"  spy guesses: {sg['guesses']} from {sg['windows']} windows, accuracy {_pct(sg['accuracy'])}",
        f"    by location: {sg['by_location'] or 'none'}",
        f"    by exchange: {sg['by_exchange'] or 'none'}",
        f"  last-chance guesses: {lc['guesses']}, accuracy {_pct(lc['accuracy'])}",
        f"  exchanges per round: mean {ex['mean']}, ran to cap {_pct(ex['ran_to_cap'])}, {ex['distribution']}",
        f"  specificity ({sp['judged']} civilian answers judged): mean {sp['mean']}, rated 1-2 {_pct(sp['share_1_2'])}, "
        f"{sp['distribution']}; fits none {sp['fits_none']}, fits the true location {_pct(sp['fits_true_location'])}",
        f"  location leaks (AI civilians): answers raw {_pct(lk['answers_raw'])} posted {_pct(lk['answers_posted'])} "
        f"of {lk['answers']}; questions raw {_pct(lk['questions_raw'])} posted {_pct(lk['questions_posted'])} "
        f"of {lk['questions']}",
        f"  repeated questions: {a['repeated_questions']['count']} ({_pct(a['repeated_questions']['rate'])})",
        f"  defaulted turns: {a['defaulted'] or 'none'}",
        "  per call type:",
    ]
    for t, c in a["calls"].items():
        lines.append(
            f"    {t:<11} {c['calls']:>4} calls ({c['retries']} retries, {c['invalid']} invalid, {c['timeouts']} "
            f"timeouts)  ${c['cost_per_game']:.4f}/game  ${c['cost_per_call'] * 1000:.3f}/1k calls  "
            f"p50 {_ms(c['latency_p50_ms'])} p95 {_ms(c['latency_p95_ms'])}  "
            f"cached {c['cached_input'] / max(1, c['input']):.0%} of {c['input']:,} in"
        )
    total = sum(c["cost_usd"] for c in a["calls"].values())
    lines.append(f"  total ${total:.4f}, ${total / max(1, a['games']):.4f} per game")
    return "\n".join(lines)
