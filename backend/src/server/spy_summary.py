"""Per-game and aggregate summaries for hidden-location self-play: how rounds end, how well each side
plays, and what each call type costs. Built from the game state and the cost log."""

import random
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from functools import lru_cache

from agents.costlog import CostLog
from agents.spy_giveaways import giveaway
from agents.spy_guess import which_place
from engine.models import GameState
from engine.modes.spy_location import (
    CIVILIAN,
    CIVILIANS,
    CLUSTER_OF,
    DRAW,
    SPY,
    exchange_cap,
    location,
    names_location,
    names_title,
    place_role,
    spy,
    tied_players,
)

from .runsummary import percentile

CALL_TYPES = ("ask", "answer", "vote", "spy_guess", "last_chance", "guess_judge", "judge", "role_judge")
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


def rounds_of(state: GameState) -> list[dict]:
    """Each voting round: who was still in, its questions, and how its vote (and any revote) went."""
    roles = {p.id: p.role for p in state.players}
    ev = state.events
    starts = [i for i, e in enumerate(ev) if e.kind == "first"] + [len(ev)]
    out, gone = [], set()
    for a, b in zip(starts, starts[1:]):
        evs = ev[a:b]
        votes = [e for e in evs if e.kind == "vote" and e.phase == "vote"]
        accused = [e for e in evs if e.kind == "accused"]
        final = accused[-1] if accused else None
        result = None if not final else ("tie" if final.target is None else roles[final.target])
        out.append(
            {
                "round": len(out) + 1,
                "alive": len(state.players) - len(gone),
                "questions": sum(e.kind == "ask" for e in evs),
                "voted": bool(votes),
                "first_vote_tie": any(e.phase == "vote" and e.target is None for e in accused),
                "revote": any(e.kind == "vote" and e.phase == "revote" for e in evs),
                "result": result,  # spy / civilian / tie (after any revote); None: no vote this round
                "civilian_votes_on_spy": sum(roles[v.actor] == CIVILIAN and roles[v.target] == SPY for v in votes),
                "civilian_votes": sum(roles[v.actor] == CIVILIAN for v in votes),
            }
        )
        if final and final.target and roles[final.target] == CIVILIAN:
            gone.add(final.target)
    return out


@lru_cache
def random_vote_lands_on_spy(alive: int, revote: bool = True, sims: int = 40000) -> float:
    """The chance a whole vote lands on the spy when every player still in votes uniformly at random for someone
    else (plurality; a tie gets one revote between the tied players when `revote`, else accuses nobody)."""
    rng = random.Random(f"baseline:{alive}:{revote}")
    hits = 0
    for _ in range(sims):
        cands = list(range(alive))  # player 0 is the spy
        for attempt in range(2 if revote else 1):
            c = Counter(rng.choice([t for t in cands if t != v] or [t for t in range(alive) if t != v])
                        for v in range(alive))  # fmt: skip
            top = max(c.values())
            leaders = [t for t, n in c.items() if n == top]
            if len(leaders) == 1:
                hits += leaders[0] == 0
                break
            cands = leaders
    return hits / sims


def game_summary(log: CostLog, game, human_seat: str, options: dict) -> dict:
    s: GameState = game.state
    roles = {p.id: p.role for p in s.players}
    names = {p.id: p.name for p in s.players}
    loc = location(s)
    human = {p.id for p in s.players if p.is_human}
    ev = s.events
    kinds = {e.kind for e in ev}
    accused = next((e for e in reversed(ev) if e.kind == "accused"), None)  # the final one (after any revote)
    first_tie = any(e.kind == "accused" and e.phase == "vote" and e.target is None for e in ev)
    revote = [e for e in ev if e.kind == "vote" and e.phase == "revote"]
    if "guess" in kinds:
        end = "guess_right" if s.winner == SPY else "guess_wrong"
    elif "last_guess" in kinds:
        end = "caught_last_right" if s.winner in (SPY, DRAW) else "caught_last_wrong"
    elif accused and accused.target is None:
        end = "tie"
    elif accused and roles[accused.target] == SPY:
        end = "caught"
    else:
        end = "wrong_vote"

    asks = [e for e in ev if e.kind == "ask"]
    questions, answers = [], []
    title = {p.id: card["title"] for p in s.players if (card := place_role(s, p.id))}  # roles on

    def said_title(e) -> bool:
        return e.actor in title and names_title(e.text, title[e.actor])

    for i, e in enumerate(asks):
        questions.append(
            {
                "actor": names[e.actor],
                "role": roles[e.actor],
                "ai": e.actor not in human,
                "text": e.text,
                "leak": roles[e.actor] == CIVILIAN and names_location(e.text, loc),
                "giveaway": giveaway(e.text, loc) if roles[e.actor] == CIVILIAN else None,
                "repeat": is_repeat(e.text, [q.text for q in asks[:i]]),
                "place_role": title.get(e.actor),
                "title_leak": said_title(e),
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
                    "giveaway": giveaway(e.text, loc) if roles[e.actor] == CIVILIAN else None,
                    "place_role": title.get(e.actor),
                    "title_leak": said_title(e),
                    "round": sum(x.kind == "first" and x.seq < e.seq for x in ev),
                }
            )
    guess = next((e for e in ev if e.kind == "guess"), None)
    last = next((e for e in ev if e.kind == "last_guess"), None)
    votes = [e for e in ev if e.kind == "vote" and e.phase == "vote"]  # the first vote; the revote is apart
    civ_votes = [v for v in votes if roles[v.actor] == CIVILIAN]
    named = lambda e: e.text.split(": ", 1)[1].removesuffix(".")  # noqa: E731
    ruled = {g["kind"]: g for g in getattr(game, "guesses", [])}  # the server's ruling on each free-text guess

    def guess_info(e, kind: str) -> dict:
        r = ruled.get(kind, {})
        words = r.get("guess", named(e))
        # right = the guess named the place: the spy wins, or (a last chance under the draw rule) a draw
        right = s.winner == SPY or (kind == "last_guess" and s.winner == DRAW)
        return {"location": words, "place": which_place(words), "rule": r.get("rule"), "right": right}

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
        "exchange_cap": exchange_cap(s),
        "rounds": (rounds := rounds_of(s)),
        "rounds_played": len(rounds),
        "spy_won_by": None
        if s.winner != SPY or guess
        else ("parity" if "Only the spy and one civilian" in ev[-2].text + ev[-1].text else "survived"),
        "guess": guess
        and {
            "exchange": len([a for a in asks if a.seq < guess.seq]),
            "round": sum(e.kind == "first" and e.seq < guess.seq for e in ev),
            **guess_info(guess, "guess"),
        },
        "last_chance": last
        and {"round": sum(e.kind == "first" and e.seq < last.seq for e in ev), **guess_info(last, "last_guess")},
        "title_first": dict(getattr(game, "title_first", {})),
        "role_shortfall": getattr(game, "role_shortfall", 0),
        "empty_passes": dict(getattr(game, "empty", {})),
        "votes": {
            "cast": len(votes),
            "civilian": len(civ_votes),
            "civilian_on_spy": sum(roles[v.target] == SPY for v in civ_votes),
            "accused_spy": not first_tie and bool(accused and accused.target and roles[accused.target] == SPY),
            "tie": first_tie,
            "final_accused_spy": bool(accused and accused.target and roles[accused.target] == SPY),
            "revote": revote
            and {
                "result": "tie" if accused.target is None else ("spy" if roles[accused.target] == SPY else "civilian"),
                "spy_was_tied": spy(s).id in tied_players(s),
            },
        }
        if votes
        else None,
        "guess_windows": game.guess_windows,
        "defaulted": dict(game.defaulted),
        "leaked_first": dict(game.leaked_first),
        "giveaway_first": dict(getattr(game, "giveaway_first", {})),
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

    def clusters(gs: list[dict], key: str) -> dict:
        """Accuracy by the true location's cluster, and where the wrong names landed."""
        by, wrong_in = defaultdict(lambda: [0, 0]), 0
        for g in gs:
            right = g[key]["right"]
            by[CLUSTER_OF[g["location"]]][0] += right
            by[CLUSTER_OF[g["location"]]][1] += 1
            wrong_in += not right and CLUSTER_OF.get(g[key].get("place") or "") == CLUSTER_OF[g["location"]]
        wrong = sum(not g[key]["right"] for g in gs)
        return {"by_cluster": {k: f"{r}/{t}" for k, (r, t) in sorted(by.items())},
                "wrong": wrong, "wrong_in_true_cluster": wrong_in}  # fmt: skip

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
    pinned, a_ids = [], defaultdict(list)
    for g in games:
        for a in g["answers"]:
            if a["role"] == CIVILIAN and a.get("fits"):
                a_ids[g["game_id"]].append(id(a))
                if {CLUSTER_OF[f] for f in a["fits"]} == {CLUSTER_OF[g["location"]]}:
                    pinned.append(id(a))
    by_n = defaultdict(lambda: [0, 0])
    outcomes_by_n = defaultdict(Counter)
    for g in games:
        by_n[g["players"]][0] += g["winner"] == SPY
        by_n[g["players"]][1] += 1
        outcomes_by_n[g["players"]][g["winner"]] += 1
    score = lambda c: _rate(2 * c[SPY] + c[DRAW], 2 * sum(c.values()))  # noqa: E731 - wins + half of draws
    revote_on = bool(games and games[0]["options"].get("tie_revote", True))
    by_round = defaultdict(list)
    for g in games:
        for r in g.get("rounds", []):
            if r["voted"]:
                by_round[r["round"]].append(r)
    guess_round = Counter(g["guess"]["round"] for g in guesses if "round" in g["guess"])
    last_round = Counter(g["last_chance"]["round"] for g in lasts if "round" in g["last_chance"])
    last_round_right = Counter(g["last_chance"]["round"] for g in lasts if g["last_chance"].get("right"))
    carded_answers = [a for a in ai_civ_answers if a.get("place_role")]
    carded_questions = [q for q in ai_civ_questions if q.get("place_role")]
    role_judged = [a for a in carded_answers if "fits_role" in a]
    spy_judged = [(g, a) for g in games for a in g["answers"] if a["role"] == SPY and a["ai"] and "fits" in a]
    guess_round_right = Counter(g["guess"]["round"] for g in guesses if "round" in g["guess"] and g["guess"]["right"])
    outcomes = Counter(g["winner"] for g in games)
    chance = [1 / (g["players"] - 1) for g in voted]
    ruled = [g[k] for g in games for k in ("guess", "last_chance") if g.get(k) and g[k].get("rule")]
    rules = {
        k: dict(Counter(g[k]["rule"] for g in games if g.get(k) and g[k].get("rule"))) for k in ("guess", "last_chance")
    }
    return {
        "type": "aggregate",
        "guess_rules": rules,
        "guess_rules_judge_share": _rate(
            sum(r["rule"] in ("judge", "judge_memo", "judge_failed") for r in ruled), len(ruled)
        ),
        "empty_passes": dict(sum((Counter(g.get("empty_passes", {})) for g in games), Counter())),
        "mode": games[0]["mode"] if games else None,
        "games": n,
        "options": games[0]["options"] if games else {},
        "human_seat": games[0]["human_seat"] if games else None,
        "spy_win_rate": _rate(sum(g["winner"] == SPY for g in games), n),
        "spy_win_rate_by_players": {k: _rate(*v) for k, v in sorted(by_n.items())},
        "outcomes": {"spy": outcomes[SPY], "civilians": outcomes[CIVILIANS], "draw": outcomes[DRAW]},
        "spy_score": score(outcomes),
        "by_players": {
            k: {"spy": c[SPY], "civilians": c[CIVILIANS], "draw": c[DRAW], "spy_score": score(c)}
            for k, c in sorted(outcomes_by_n.items())
        },
        "rounds": {
            "mean": round(sum(g.get("rounds_played", 1) for g in games) / n, 2) if n else None,
            "distribution": dict(sorted(Counter(g.get("rounds_played", 1) for g in games).items())),
            "questions_per_game": round(sum(g["exchanges"] for g in games) / n, 2) if n else None,
            "spy_won_by": dict(Counter(g.get("spy_won_by") for g in games if g.get("spy_won_by"))),
            "by_round": {
                k: {
                    "votes": len(rs),
                    "alive": dict(sorted(Counter(r["alive"] for r in rs).items())),
                    "landed_on_spy": _rate(sum(r["result"] == SPY for r in rs), len(rs)),
                    "random_baseline": round(
                        sum(random_vote_lands_on_spy(r["alive"], revote_on) for r in rs) / len(rs), 3
                    ),
                    "on_civilian": _rate(sum(r["result"] == CIVILIAN for r in rs), len(rs)),
                    "tie_after_revote": _rate(sum(r["result"] == "tie" for r in rs), len(rs)),
                    "first_vote_tie": _rate(sum(r["first_vote_tie"] for r in rs), len(rs)),
                    "civilian_votes_on_spy": _rate(
                        sum(r["civilian_votes_on_spy"] for r in rs), sum(r["civilian_votes"] for r in rs)
                    ),
                }
                for k, rs in sorted(by_round.items())
            },
            "all_votes": {
                "votes": sum(map(len, by_round.values())),
                "first_vote_tie": _rate(
                    sum(r["first_vote_tie"] for rs in by_round.values() for r in rs), sum(map(len, by_round.values()))
                ),
            },
            "guess_by_round": {k: f"{guess_round_right[k]}/{t}" for k, t in sorted(guess_round.items())},
            "last_chance_by_round": {k: f"{last_round_right[k]}/{t}" for k, t in sorted(last_round.items())},
        },
        "vote_tie_rate": _rate(sum(g["votes"]["tie"] for g in voted), len(voted)),
        "revotes": dict(Counter(g["votes"]["revote"]["result"] for g in voted if g["votes"].get("revote"))),
        "final_accused_spy": _rate(sum(g["votes"]["final_accused_spy"] for g in voted), len(voted)),
        "ends": {k: ends[k] for k in sorted(ends)},
        "tie_rate": _rate(ends["tie"], n),
        "vote": {
            "rounds_voted": len(voted),
            "reached_vote": _rate(len(voted), n),
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
            **clusters(guesses, "guess"),
        },
        "last_chance": {
            "guesses": len(lasts),
            "accuracy": _rate(sum(g["last_chance"]["right"] for g in lasts), len(lasts)),
            **clusters(lasts, "last_chance"),
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
        "roles": {
            "answers": len(carded_answers),
            "title_answers_raw": _rate(
                sum(g.get("title_first", {}).get("answer", 0) for g in games), len(carded_answers)
            ),
            "title_answers_posted": _rate(sum(a["title_leak"] for a in carded_answers), len(carded_answers)),
            "title_questions_raw": _rate(
                sum(g.get("title_first", {}).get("ask", 0) for g in games), len(carded_questions)
            ),
            "title_questions_posted": _rate(sum(q["title_leak"] for q in carded_questions), len(carded_questions)),
            "judged": len(role_judged),
            "fits_role": _rate(sum(a["fits_role"] for a in role_judged), len(role_judged)),
            "fits_place": _rate(sum(a["fits_place"] for a in role_judged), len(role_judged)),
            "fits_both": _rate(sum(a["fits_role"] and a["fits_place"] for a in role_judged), len(role_judged)),
        },
        "spy_answers": {  # the offline fits judge on the AI spy's answers: do they fit the true place?
            "judged": len(spy_judged),
            "fit_true_place": _rate(sum(g["location"] in a["fits"] for g, a in spy_judged), len(spy_judged)),
            "mean_fits": round(sum(len(a["fits"]) for _, a in spy_judged) / len(spy_judged), 1) if spy_judged else None,
        },
        "giveaway": {
            "answers_raw": _rate(sum(g.get("giveaway_first", {}).get("answer", 0) for g in games), len(ai_civ_answers)),
            "answers_posted": _rate(sum(bool(a.get("giveaway")) for a in ai_civ_answers), len(ai_civ_answers)),
            "questions_raw": _rate(
                sum(g.get("giveaway_first", {}).get("ask", 0) for g in games), len(ai_civ_questions)
            ),
            "questions_posted": _rate(sum(bool(q.get("giveaway")) for q in ai_civ_questions), len(ai_civ_questions)),
            "top_posted_words": Counter(
                x["giveaway"] for x in ai_civ_answers + ai_civ_questions if x.get("giveaway")
            ).most_common(10),
        },
        "cluster_only": {  # judged civilian answers whose every fitting place is in the true cluster
            "answers": _rate(len(pinned), len(judged)),
            "games_with_one": sum(any(p in pinned for p in a_ids[g["game_id"]]) for g in games),
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
    who = {SPY: "the spy wins", CIVILIANS: "the civilians win", DRAW: "a draw"}.get(g["winner"], str(g["winner"]))
    return (
        f"{g['game_id']}: {who} ({how}), {g['players']} players, location {g['location']}, "
        f"spy {g['spy']}, {g['exchanges']}/{g['exchange_cap']} exchanges, ${cost:.4f}"
    )


def _rounds_lines(a: dict) -> list[str]:
    r = a.get("rounds")
    if not r:
        return []
    lines = [
        f"  rounds: mean {r['mean']} {r['distribution']}; questions per game {r['questions_per_game']}; "
        f"spy won by {r['spy_won_by'] or 'none'}; spy guesses right/made by round {r['guess_by_round'] or 'none'}; "
        f"last chances right/made by round {r.get('last_chance_by_round') or 'none'}",
        f"  first-vote ties: {_pct(r['all_votes']['first_vote_tie'])} of {r['all_votes']['votes']} votes",
    ]
    for k, b in r["by_round"].items():
        lines.append(
            f"    round {k}: {b['votes']} votes (players in {b['alive']}), landed on the spy {_pct(b['landed_on_spy'])} "
            f"vs random {_pct(b['random_baseline'])}; on a civilian {_pct(b['on_civilian'])}; tied after revote "
            f"{_pct(b['tie_after_revote'])}; first vote tied {_pct(b['first_vote_tie'])}; civilian ballots on the "
            f"spy {_pct(b['civilian_votes_on_spy'])}"
        )
    return lines


def format_aggregate(a: dict) -> str:
    v, sg, lc, ex, sp, lk = a["vote"], a["spy_guess"], a["last_chance"], a["exchanges"], a["specificity"], a["leak"]
    lines = [
        f"AGGREGATE over {a['games']} games ({a['mode']}, human seat: {a['human_seat']}, options {a['options']})",
        f"  outcomes: spy {a['outcomes']['spy']} / civilians {a['outcomes']['civilians']} / draws "
        f"{a['outcomes']['draw']}; spy win rate {_pct(a['spy_win_rate'])}, spy score {_pct(a['spy_score'])}",
        "  by players: "
        + "; ".join(
            f"{k}p {b['spy']}/{b['civilians']}/{b['draw']} (score {_pct(b['spy_score'])})"
            for k, b in a["by_players"].items()
        ),
        *_rounds_lines(a),
        f"  vote ties {_pct(a['vote_tie_rate'])} of first votes; revotes {a['revotes'] or 'none'}; "
        f"final vote found the spy {_pct(a['final_accused_spy'])}",
        "  how rounds ended: "
        + ", ".join(f"{k} {c}" for k, c in a["ends"].items())
        + f"; tie rate {_pct(a['tie_rate'])}",
        f"  reached a vote: {_pct(v.get('reached_vote'))} of games",
        f"  vote: accused the spy in {_pct(v['accused_spy'])} of {v['rounds_voted']} votes; civilian votes on the spy "
        f"{_pct(v['civilian_votes_on_spy'])} vs chance {_pct(v['chance'])}",
        f"  spy guesses: {sg['guesses']} from {sg['windows']} windows, accuracy {_pct(sg['accuracy'])}",
        f"    by location: {sg['by_location'] or 'none'}",
        f"    by exchange: {sg['by_exchange'] or 'none'}",
        f"    by cluster: {sg.get('by_cluster')}; wrong {sg.get('wrong')}, "
        f"of which in the true cluster {sg.get('wrong_in_true_cluster')}",
        f"  guess rulings: spy guesses {a.get('guess_rules', {}).get('guess')}, last chances "
        f"{a.get('guess_rules', {}).get('last_chance')}; judge-decided {_pct(a.get('guess_rules_judge_share'))}; "
        f"empty replies passed {a.get('empty_passes') or 'none'}",
        f"  last-chance guesses: {lc['guesses']}, accuracy {_pct(lc['accuracy'])}; by cluster {lc.get('by_cluster')}; "
        f"wrong {lc.get('wrong')}, of which in the true cluster {lc.get('wrong_in_true_cluster')}",
        f"  exchanges per round: mean {ex['mean']}, ran to cap {_pct(ex['ran_to_cap'])}, {ex['distribution']}",
        f"  specificity ({sp['judged']} civilian answers judged): mean {sp['mean']}, rated 1-2 {_pct(sp['share_1_2'])}, "
        f"{sp['distribution']}; fits none {sp['fits_none']}, fits the true location {_pct(sp['fits_true_location'])}",
        f"  location leaks (AI civilians): answers raw {_pct(lk['answers_raw'])} posted {_pct(lk['answers_posted'])} "
        f"of {lk['answers']}; questions raw {_pct(lk['questions_raw'])} posted {_pct(lk['questions_posted'])} "
        f"of {lk['questions']}",
        f"  giveaway words (AI civilians): answers raw {_pct(a['giveaway']['answers_raw'])} posted "
        f"{_pct(a['giveaway']['answers_posted'])}; questions raw {_pct(a['giveaway']['questions_raw'])} posted "
        f"{_pct(a['giveaway']['questions_posted'])}; top posted {a['giveaway']['top_posted_words']}",
        f"  answers that fit only the true cluster: {_pct(a['cluster_only']['answers'])}; games with at least one: "
        f"{a['cluster_only']['games_with_one']}/{a['games']}",
        f"  role titles said (AI civilians, {a['roles']['answers']} answers): answers raw "
        f"{_pct(a['roles']['title_answers_raw'])} posted {_pct(a['roles']['title_answers_posted'])}; questions raw "
        f"{_pct(a['roles']['title_questions_raw'])} posted {_pct(a['roles']['title_questions_posted'])}",
        f"  role consistency ({a['roles']['judged']} judged): fits own role {_pct(a['roles']['fits_role'])}, fits "
        f"the place {_pct(a['roles']['fits_place'])}, both {_pct(a['roles']['fits_both'])}",
        f"  spy answers ({a['spy_answers']['judged']} judged): fit the true place {_pct(a['spy_answers']['fit_true_place'])},"
        f" mean places fitted {a['spy_answers']['mean_fits']}",
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
