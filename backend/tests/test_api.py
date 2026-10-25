"""Game setup through the API, with the fake model (no network)."""

import os

os.environ["FAKE_LLM"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from agents.costlog import CostLog  # noqa: E402
from agents.llm import FakeLLM  # noqa: E402
from agents.runner import AgentRunner  # noqa: E402
from server import app as app_module  # noqa: E402
from server.settings import Settings  # noqa: E402

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Fake model and a throwaway cost log, so tests never touch kira.db."""
    settings = Settings(db_path=tmp_path / "t.db", fake_llm=True)
    runner = AgentRunner(FakeLLM(), settings, CostLog(settings.db_path))
    monkeypatch.setattr(app_module, "get_runner", lambda: runner)
    app_module.started.clear()


def test_chosen_cast_traits_difficulty_and_roles():
    r = client.post(
        "/api/games",
        json={
            "name": "Alex",
            "cast": ["bram", "odile", "kit", "juno", "hollis"],
            "traits": {"bram": {"talkative": 0.1, "suspicious": 0.1, "liar": 0.9}},
            "difficulty": "merciless",
            "roles": ["jester", "bodyguard"],
        },
    )
    assert r.status_code == 200, r.text
    game = app_module.games[r.json()["game_id"]]
    names = sorted(p.name for p in game.state.players if not p.is_human)
    assert names == ["Bram", "Hollis", "Juno", "Kit", "Odile"]
    roles = [p.role for p in game.state.players]
    assert "jester" in roles and "bodyguard" in roles
    bram = next(p for p in game.personas.values() if p.id == "bram")
    assert bram.traits.liar == 0.9 and bram.strategy  # explicit knobs win; merciless adds a strategy
    odile = next(p for p in game.personas.values() if p.id == "odile")
    assert odile.traits.liar == 0.85  # 0.6 shifted by merciless
    game.task.cancel()


def test_smallest_table_takes_both_optional_roles():
    r = client.post("/api/games", json={"name": "Alex", "opponents": 4, "roles": ["jester", "bodyguard"]})
    assert r.status_code == 200, r.text
    game = app_module.games[r.json()["game_id"]]
    assert sorted(p.role for p in game.state.players) == ["bodyguard", "detective", "doctor", "jester", "mafia"]
    game.task.cancel()


def test_duplicate_optional_role_is_rejected():
    r = client.post("/api/games", json={"name": "Alex", "roles": ["jester", "jester"]})
    assert r.status_code == 422


def test_bad_cast_is_rejected():
    assert client.post("/api/games", json={"name": "A", "cast": ["bram", "bram", "kit", "juno"]}).status_code == 422
    assert client.post("/api/games", json={"name": "A", "cast": ["nobody", "kit", "juno", "odile"]}).status_code == 422


def test_cast_endpoint_lists_all_eight():
    ids = [c["id"] for c in client.get("/api/cast").json()]
    assert len(ids) == 8 and "hollis" in ids


def test_difficulty_presets_are_listed():
    d = client.get("/api/difficulty").json()
    assert set(d) == {"cozy", "tricky", "merciless"} and d["tricky"] == {"suspicious": 0.0, "liar": 0.0}
