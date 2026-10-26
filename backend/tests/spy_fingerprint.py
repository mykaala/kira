"""Fingerprints of whole fake games (who asked whom, every vote, guess and outcome), so a rules change can be
checked to leave the single-vote game exactly as it was. Run as a script to record them:
    uv run python tests/spy_fingerprint.py"""

import asyncio
import json
import os
import random
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["FAKE_LLM"] = "1"
sys.path.insert(0, str(Path(__file__).parent))

from spy_bots import play_spy  # noqa: E402

from agents.costlog import CostLog  # noqa: E402
from agents.spy_fake import SpyFakeLLM  # noqa: E402
from agents.spy_runner import SpyRunner  # noqa: E402
from engine.modes.spy_location import CIVILIAN, SPY, location  # noqa: E402
from server.settings import Settings  # noqa: E402
from server.spy_game import SpyGame  # noqa: E402

FILE = Path(__file__).parent / "data" / "spy_k1_fingerprints.json"
KINDS = ("first", "ask", "answer", "vote", "accused", "guess", "last_guess", "outcome")


def fingerprint(state, void=None) -> dict:
    return {
        "winner": state.winner,
        "void": bool(void),
        "place": location(state),
        "spy": next(p.id for p in state.players if p.role == SPY),
        "events": [[e.kind, e.actor, e.target] for e in state.events if e.kind in KINDS],
    }


def _runner(tmp: Path, seed: int) -> SpyRunner:
    s = Settings(_env_file=None, db_path=tmp / f"{seed}.db", fake_llm=True, connect_backoff_s=[])
    return SpyRunner(SpyFakeLLM(seed=seed, leak_rate=0.1), s, CostLog(s.db_path), memo_path=tmp / f"{seed}.json")


async def _headless(tmp: Path, seat: str, seed: int) -> dict:
    r = _runner(tmp, seed)
    g = SpyGame(runner=r, log=r.log, players=5 + seed % 4, human_seat=seat, seed=seed)
    await g.run()
    return fingerprint(g.state, g.void)


async def _live(tmp: Path, role: str, seed: int) -> dict:
    from test_spy_live import default_move, new_live, play

    g = new_live(tmp, role=role, seed=seed, players=5 + seed % 4, runner=_runner(tmp, seed))
    await play(g, default_move, seed=seed)
    return fingerprint(g.state, g.void)


def record() -> dict:
    with TemporaryDirectory() as d:
        tmp = Path(d)
        out = {"bots": [fingerprint(play_spy(s, n=5 + s % 4)) for s in range(100)]}
        for seat in ("ai", "bot"):
            out[f"headless_{seat}"] = [asyncio.run(_headless(tmp, seat, s)) for s in range(30)]
        for role in (SPY, CIVILIAN):
            out[f"live_{role}"] = [asyncio.run(_live(tmp, role, s)) for s in range(15)]
    return out


if __name__ == "__main__":
    random.seed(0)
    FILE.write_text(json.dumps(record()))
    print(f"wrote {FILE}")
