"""Headless all-AI games for the milestone gate: python -m server.selfplay --games 20
Each game's summary (and transcript) is appended to runs/<timestamp>.jsonl, followed by
an aggregate line when more than one game is played."""

import argparse
import asyncio
import json
import time

from .deps import get_runner
from .orchestrator import Game
from .runsummary import aggregate, format_summary, game_summary, transcript
from .settings import BACKEND, get_settings


async def main(n_games: int, opponents: int, quiet: bool, parallel: int) -> None:
    settings = get_settings()
    runner = get_runner()
    runs = BACKEND / "runs"
    runs.mkdir(exist_ok=True)
    out = runs / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    sem = asyncio.Semaphore(parallel)
    summaries: list[dict] = []
    stopped: list[str] = []  # set once the model API is unreachable; later games don't start

    def write(record: dict) -> None:
        with out.open("a") as f:
            f.write(json.dumps(record) + "\n")

    async def one(i: int) -> None:
        async with sem:
            if stopped:
                return
            game = Game(runner=runner, log=runner.log, opponents=opponents, human_name=None)
            game.printer = lambda k, e: None
            await game.run()
            if game.aborted:
                stopped.append(game.aborted)
                print(f"\n[{i + 1}/{n_games}] {game.id}: STOPPED, {game.aborted}. Not counted.", flush=True)
                return
            s = game_summary(runner.log, settings, game.id, game.state, fake=settings.fake_llm)
            summaries.append(s)
            write(s)
            if not quiet:
                print("\n".join(transcript(game.state)))
            print(f"\n[{i + 1}/{n_games}] " + format_summary(s), flush=True)

    await asyncio.gather(*(one(i) for i in range(n_games)))
    if stopped:
        print(f"\nRun stopped early: the model API was unreachable. {len(summaries)} complete games are summarized.")
    if len(summaries) > 1:
        agg = aggregate(runner.log, settings, summaries)
        write(agg)
        print("\n" + format_summary(agg))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    import sys

    if "--mode" in sys.argv:  # --mode spy_location hands the rest of the arguments to that mode's self-play
        i = sys.argv.index("--mode")
        if sys.argv[i + 1] == "spy_location":
            from .spy_selfplay import run

            run(sys.argv[1:i] + sys.argv[i + 2 :])
            raise SystemExit
        if sys.argv[i + 1] != "mafia":
            raise SystemExit(f"unknown mode {sys.argv[i + 1]!r}: mafia or spy_location")
        del sys.argv[i : i + 2]
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1)
    ap.add_argument("--opponents", type=int, default=6, help="AI players besides the human's seat")
    ap.add_argument("--parallel", type=int, default=1, help="games to run at once")
    ap.add_argument("--quiet", action="store_true", help="don't print transcripts (default when --games > 1)")
    a = ap.parse_args()
    asyncio.run(main(a.games, a.opponents, a.quiet or a.games > 1, a.parallel))
