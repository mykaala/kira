"""Golden Mafia games at the engine level: seeded random-bot games (human interjections, claims and
every optional role included), saved in full. test_golden.py covers the orchestrator and agents; this
covers the engine calls directly, so engine work for another game must leave both byte-identical.

If a change to Mafia is intended, regenerate with:  UPDATE_GOLDEN=1 uv run pytest tests/test_golden_engine.py
and review the diff before committing it."""

import json
import os
from pathlib import Path

import pytest
from bots import play_random

GOLDEN = Path(__file__).parent / "golden"
GAMES = [(101, 5, ()), (202, 7, ()), (303, 9, ()), (404, 8, ("jester",)), (505, 8, ("bodyguard",))]


def play(seed: int, n: int, extras: tuple[str, ...]) -> dict:
    s = play_random(seed, n=n, extra_roles=extras)
    return {
        "seed": seed,
        "winner": s.winner,
        "days": s.day,
        "players": [p.model_dump() for p in s.players],
        "events": [e.model_dump() for e in s.events],
        "claims": [c.model_dump() for c in s.claims],
    }


@pytest.mark.parametrize("seed,n,extras", GAMES)
def test_golden_engine_game_is_unchanged(seed, n, extras):
    got = json.dumps(play(seed, n, extras), indent=1, sort_keys=True) + "\n"
    path = GOLDEN / f"mafia-bots-seed{seed}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(got)
    assert path.exists(), f"missing {path.name}: run with UPDATE_GOLDEN=1 once"
    assert got == path.read_text(), f"{path.name} changed: Mafia behaviour is frozen"
