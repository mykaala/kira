"""Golden Mafia games: three seeded all-AI games with the fake model, saved in full (every event,
secrets included, plus claims). Engine work for another game must leave these byte-identical.

If a change to Mafia is intended, regenerate with:  UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py
and review the diff before committing it."""

import asyncio
import json
import os
from pathlib import Path

import pytest

from agents.costlog import CostLog
from agents.llm import FakeLLM
from agents.runner import AgentRunner
from engine.engine import MODES
from server.orchestrator import Game
from server.settings import Settings

GOLDEN = Path(__file__).parent / "golden"
SEEDS = [11, 22, 33]


def play(seed: int, tmp_path: Path) -> dict:
    MODES["mafia"].reveal_role_on_death = False  # the default, pinned so other tests can't leak in
    settings = Settings(_env_file=None, db_path=tmp_path / f"golden-{seed}.db", fake_llm=True)
    runner = AgentRunner(FakeLLM(seed=seed, delay_s=0), settings, CostLog(settings.db_path))
    game = Game(runner=runner, log=runner.log, opponents=6, human_name=None, seed=seed)
    game.printer = lambda kind, event: None
    asyncio.run(game.run())
    s = game.state
    return {
        "seed": seed,
        "winner": s.winner,
        "days": s.day,
        "players": [p.model_dump() for p in s.players],
        "events": [e.model_dump() for e in s.events],
        "claims": [c.model_dump() for c in s.claims],
    }


@pytest.mark.parametrize("seed", SEEDS)
def test_golden_game_is_unchanged(seed, tmp_path):
    got = json.dumps(play(seed, tmp_path), indent=1, sort_keys=True) + "\n"
    path = GOLDEN / f"mafia-seed{seed}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(got)
    assert path.exists(), f"missing {path.name}: run with UPDATE_GOLDEN=1 once"
    assert got == path.read_text(), f"{path.name} changed: Mafia behaviour is frozen"


def test_golden_games_are_deterministic(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert play(SEEDS[0], tmp_path / "a") == play(SEEDS[0], tmp_path / "b")
