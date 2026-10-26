"""Headless hidden-location games: python -m server.spy_selfplay --games 40 [--parallel 4]
(or server.selfplay --mode spy_location). Player counts cycle 5, 6, 7, 8. After the games, an offline
judge rates every civilian answer's specificity (skip with --no-judge). Each game's summary goes to
runs/<timestamp>-spy.jsonl, then an aggregate line."""

import argparse
import asyncio
import json
import time

from agents.costlog import CostLog
from agents.llm import OpenAILLM
from agents.spy_fake import SpyFakeLLM
from agents.spy_judge import judge_answers, judge_roles
from agents.spy_runner import SpyRunner
from engine.modes.spy_location import CIVILIAN, SPY_MODE, configure
from engine.modes.spy_roles import ROLES

from .settings import BACKEND, get_settings
from .spy_game import SpyGame
from .spy_summary import aggregate, format_aggregate, format_game, game_summary

PLAYER_COUNTS = [5, 6, 7, 8]


async def main(
    n_games: int,
    parallel: int,
    human_seat: str,
    options: dict,
    judge: bool,
    seed: int | None,
    quiet: bool,
    indices: list[int] | None = None,
) -> None:
    settings = get_settings()
    if settings.fake_llm:
        llm = SpyFakeLLM(seed=seed or 0)
    elif settings.openai_api_key:
        llm = OpenAILLM(settings.openai_api_key)
    else:
        raise SystemExit("OPENAI_API_KEY is not set: add it to backend/.env, or set FAKE_LLM=1")
    log = CostLog(settings.db_path)
    # the fake model's rulings never go in the real judge memo
    memo = BACKEND / "runs" / ("spy_guess_memo-fake.json" if settings.fake_llm else "spy_guess_memo.json")
    runner = SpyRunner(llm, settings, log, memo_path=memo)
    configure(**options)
    options = dict(SPY_MODE.options)  # every switch, saved in each game's summary

    runs = BACKEND / "runs"
    runs.mkdir(exist_ok=True)
    out = runs / f"{time.strftime('%Y%m%d-%H%M%S')}-spy.jsonl"
    sem = asyncio.Semaphore(parallel)
    summaries: list[dict] = []
    stopped: list[str] = []
    voided: list[str] = []  # games that couldn't be decided fairly (an empty last chance); not counted

    async def one(i: int) -> None:
        async with sem:
            if stopped:
                return
            game = SpyGame(
                runner=runner,
                log=log,
                players=PLAYER_COUNTS[i % len(PLAYER_COUNTS)],
                human_seat=human_seat,
                seed=None if seed is None else seed + i,
            )
            await game.run()
            if game.void:
                voided.append(game.id)
                print(f"[{i + 1}/{n_games}] {game.id}: VOID, {game.void}. Not counted.", flush=True)
                return
            if game.aborted:
                stopped.append(game.aborted)
                print(f"[{i + 1}/{n_games}] {game.id}: STOPPED, {game.aborted}. Not counted.", flush=True)
                return
            s = game_summary(log, game, human_seat, options)
            summaries.append(s)
            if not quiet:
                print("\n".join(s["transcript"]))
            print(f"[{i + 1}/{n_games}] " + format_game(s), flush=True)

    await asyncio.gather(*(one(i) for i in (indices if indices is not None else range(n_games))))
    summaries.sort(key=lambda s: s["game_id"])
    if judge:
        items = [(s, a) for s in summaries for a in s["answers"]]  # the spy's too: do they fit the true place?
        print(f"judging {len(items)} answers...", flush=True)
        rated = await judge_answers(
            llm,
            settings,
            log,
            [{"game_id": s["game_id"], "question": a["question"], "answer": a["answer"]} for s, a in items],
        )
        for (_, a), r in zip(items, rated):
            a.update(r)
        carded = [(s, a) for s in summaries for a in s["answers"] if a["role"] == CIVILIAN and a.get("place_role")]
        if carded:
            print(f"judging {len(carded)} civilian answers against their roles...", flush=True)
            cards = {(p, r["title"]): r for p, rs in ROLES.items() for r in rs}
            ruled = await judge_roles(
                llm,
                settings,
                log,
                [
                    {
                        "game_id": s["game_id"],
                        "place": s["location"],
                        "card": cards[(s["location"], a["place_role"])],
                        "question": a["question"],
                        "answer": a["answer"],
                    }  # fmt: skip
                    for s, a in carded
                ],
            )
            for (_, a), r in zip(carded, ruled):
                a.update(r)
    with out.open("w") as f:
        for s in summaries:
            f.write(json.dumps(s) + "\n")
        if summaries:
            agg = aggregate(log, summaries) | {
                "voided_games": voided,
                "guess_memo": runner.matcher.memo,  # every judge verdict so far, kept across runs
            }
            f.write(json.dumps(agg) + "\n")
            print("\n" + format_aggregate(agg))
    if stopped:
        print(f"\nRun stopped early: the model API was unreachable. {len(summaries)} complete games are summarized.")
    print(f"\nwritten to {out}")


def run(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=1, help="games to run at once")
    ap.add_argument("--human-seat", choices=["ai", "bot"], default="ai")
    # defaults come from the mode's options (the play config); each switch overrides one
    o = SPY_MODE.options
    flag = argparse.BooleanOptionalAction
    ap.add_argument("--last-chance", action=flag, default=o["last_chance_guess"], help="a caught spy may still guess")
    ap.add_argument("--shortlist", action=flag, default=o["last_chance_shortlist"], help="last chance from 5 places")
    ap.add_argument("--asks-per-player", type=int, default=o["asks_per_player"], help="questions per round")
    ap.add_argument("--survive-votes", type=int, default=o["spy_survive_votes"], help="votes the spy must survive")
    ap.add_argument("--roles", action=flag, default=o["roles"], help="civilians get a secret role at the place")
    ap.add_argument("--min-generic-roles", type=int, default=o["min_generic_roles_per_game"])
    ap.add_argument("--ask-angle", action=flag, default=o["ask_angle"], help="a seeded topic for each ask turn")
    ap.add_argument("--giveaway-check", action=flag, default=o["giveaway_check"], help="retry giveaway words")
    ap.add_argument("--tie-revote", action=flag, default=o["tie_revote"], help="one revote between tied players")
    ap.add_argument("--last-chance-result", choices=["spy_wins", "draw"], default=o["last_chance_result"])
    ap.add_argument("--no-judge", action="store_true", help="skip the offline specificity judge")
    ap.add_argument("--seed", type=int, help="game i uses seed + i (default: random)")
    ap.add_argument("--indices", type=int, nargs="+", help="run only these game numbers (0-based) of --games")
    ap.add_argument("--quiet", action="store_true", help="don't print transcripts (default when --games > 1)")
    a = ap.parse_args(argv)
    asyncio.run(
        main(
            a.games,
            a.parallel,
            a.human_seat,
            {
                "last_chance_guess": a.last_chance,
                "last_chance_shortlist": a.shortlist,
                "asks_per_player": a.asks_per_player,
                "spy_survive_votes": a.survive_votes,
                "roles": a.roles,
                "min_generic_roles_per_game": a.min_generic_roles,
                "ask_angle": a.ask_angle,
                "giveaway_check": a.giveaway_check,
                "tie_revote": a.tie_revote,
                "last_chance_result": a.last_chance_result,
            },
            not a.no_judge,
            a.seed,
            a.quiet or a.games > 1,
            a.indices,
        )
    )


if __name__ == "__main__":
    run()
