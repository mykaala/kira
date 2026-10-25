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
from agents.spy_judge import judge_answers
from agents.spy_runner import SpyRunner
from engine.modes.spy_location import CIVILIAN, SPY_MODE

from .settings import BACKEND, get_settings
from .spy_game import SpyGame
from .spy_summary import aggregate, format_aggregate, format_game, game_summary

PLAYER_COUNTS = [5, 6, 7, 8]


async def main(
    n_games: int,
    parallel: int,
    human_seat: str,
    last_chance: bool,
    shortlist: bool,
    judge: bool,
    seed: int | None,
    quiet: bool,
) -> None:
    settings = get_settings()
    if settings.fake_llm:
        llm = SpyFakeLLM(seed=seed or 0)
    elif settings.openai_api_key:
        llm = OpenAILLM(settings.openai_api_key)
    else:
        raise SystemExit("OPENAI_API_KEY is not set: add it to backend/.env, or set FAKE_LLM=1")
    log = CostLog(settings.db_path)
    runner = SpyRunner(llm, settings, log)
    SPY_MODE.options["last_chance_guess"] = last_chance
    SPY_MODE.options["last_chance_shortlist"] = shortlist
    options = {k: SPY_MODE.options[k] for k in ("last_chance_guess", "last_chance_shortlist")}

    runs = BACKEND / "runs"
    runs.mkdir(exist_ok=True)
    out = runs / f"{time.strftime('%Y%m%d-%H%M%S')}-spy.jsonl"
    sem = asyncio.Semaphore(parallel)
    summaries: list[dict] = []
    stopped: list[str] = []

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
            if game.aborted:
                stopped.append(game.aborted)
                print(f"[{i + 1}/{n_games}] {game.id}: STOPPED, {game.aborted}. Not counted.", flush=True)
                return
            s = game_summary(log, game, human_seat, options)
            summaries.append(s)
            if not quiet:
                print("\n".join(s["transcript"]))
            print(f"[{i + 1}/{n_games}] " + format_game(s), flush=True)

    await asyncio.gather(*(one(i) for i in range(n_games)))
    summaries.sort(key=lambda s: s["game_id"])
    if judge:
        items = [(s, a) for s in summaries for a in s["answers"] if a["role"] == CIVILIAN]
        print(f"judging {len(items)} civilian answers...", flush=True)
        rated = await judge_answers(
            llm,
            settings,
            log,
            [{"game_id": s["game_id"], "question": a["question"], "answer": a["answer"]} for s, a in items],
        )
        for (_, a), r in zip(items, rated):
            a.update(r)
    with out.open("w") as f:
        for s in summaries:
            f.write(json.dumps(s) + "\n")
        if summaries:
            agg = aggregate(log, summaries)
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
    ap.add_argument("--no-last-chance", action="store_true", help="turn off the caught spy's last-chance guess")
    ap.add_argument("--shortlist", action="store_true", help="last-chance guess from 5 locations, not all 20")
    ap.add_argument("--no-judge", action="store_true", help="skip the offline specificity judge")
    ap.add_argument("--seed", type=int, help="game i uses seed + i (default: random)")
    ap.add_argument("--quiet", action="store_true", help="don't print transcripts (default when --games > 1)")
    a = ap.parse_args(argv)
    asyncio.run(
        main(
            a.games,
            a.parallel,
            a.human_seat,
            not a.no_last_chance,
            a.shortlist,
            not a.no_judge,
            a.seed,
            a.quiet or a.games > 1,
        )
    )


if __name__ == "__main__":
    run()
