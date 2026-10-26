"""Nothing the browser receives gives away a secret before the game ends. Every payload the event stream would
send (serialized exactly as app.events does) is scanned over hundreds of fake-model games:
- a human spy never sees the place, anyone else's role, or any AI's notes or plan;
- a human civilian sees the place only in their own role card (status.secret);
- the only role ever shown is "civilian" for a player voted out;
- with roles on, nobody's role at the place but your own (in status.secret) is in any payload until the end.
Every GET route is listed here, so a new endpoint fails this test until it is checked."""

import asyncio
import json
import os
import re

os.environ["FAKE_LLM"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from test_spy_live import default_move, make_runner, new_live, play  # noqa: E402

from agents.spy_fake import SpyFakeLLM  # noqa: E402
from engine.modes.spy_location import (  # noqa: E402
    CIVILIAN,
    LOCATIONS,
    PLACE_ROLE,
    SPY,
    SPY_MODE,
    configure,
    location,
    names_title,
    place_role,
)
from server import app as app_module  # noqa: E402

GAMES = 200
PRIVATE_WORDS = ("intent", "guess_window", "probe", "vague", "blend", "suspicion", "beliefs", "persona", "strategy")


def place_words(place: str) -> list[str]:
    return [place, *LOCATIONS[place]]


def scan(role: str, seed: int, tmp_path) -> int:
    """Play one game with a scripted person; check every payload up to the end. Returns payloads checked."""
    runner = make_runner(tmp_path, SpyFakeLLM(seed=seed, leak_rate=0))  # AI speech never names it on purpose
    game = new_live(tmp_path, role=role, seed=seed, players=5 + seed % 4, runner=runner)
    place = location(game.state)
    others = [e.text for e in game.state.events if e.kind == PLACE_ROLE and e.target != game.human]
    checked = [0]
    done = [False]
    outs = [0]

    def check(kind: str, data: dict, g) -> None:
        if done[0]:
            return
        if kind == "event" and data["kind"] in ("guess", "last_guess", "outcome", "game_over"):
            done[0] = True  # a guess is ruled and answered at once: from here on the secrets are the results
            return
        if kind == "reveal" or (kind == "status" and data["over"]):
            done[0] = True
            return
        payload = dict(data)
        if kind == "status":
            if role == CIVILIAN:
                card = place_role(g.state, g.human)
                assert payload["secret"] == ({"place": place, "role": card} if card else {"place": place})
            else:
                assert payload["secret"] == {"spy": True}
            payload.pop("secret")
            for p in payload["players"]:
                if p["id"] != g.human and p["alive"]:
                    assert p["role"] is None, f"{p['name']}'s role shows: {p['role']}"
                elif p["id"] != g.human:  # voted out: shown as a civilian, the one exception, and always true
                    assert p["role"] == CIVILIAN == g.state.player(p["id"]).role
                    outs[0] += 1
            assert payload["players"][[p["id"] for p in payload["players"]].index(g.human)]["role"] == role
        text = json.dumps(payload).lower()  # exactly what the stream would carry
        for w in place_words(place):
            assert not re.search(rf"\b{re.escape(w)}\b", text), (kind, w, data)
        for w in PRIVATE_WORDS:
            assert w not in text, (kind, w, data)
        for t in others:  # roles on: anyone else's role at the place
            assert not names_title(text, t), (kind, t, data)
        checked[0] += 1

    asyncio.run(play(game, default_move, seed=seed, on_payload=check))
    scan.outs += outs[0] > 0
    return checked[0]


scan.outs = 0  # games where a voted-out player was shown


@pytest.mark.parametrize("roles", [False, True])
@pytest.mark.parametrize("role", [SPY, CIVILIAN])
def test_no_payload_gives_away_a_secret(role, roles, tmp_path):
    before = dict(SPY_MODE.options)
    configure(roles=roles)
    try:
        _scan_many(role, tmp_path)
    finally:
        configure(**before)


def _scan_many(role, tmp_path):
    scan.outs = 0
    total = sum(scan(role, seed, tmp_path) for seed in range(GAMES if role == SPY else GAMES // 2))
    assert total > GAMES * 10 and scan.outs > 10


def test_every_get_route_is_known_and_secret_free(tmp_path, monkeypatch):
    """The GET routes; none takes a game id except the event stream, whose payloads are scanned above."""
    gets = {r.path for r in app_module.app.routes if "GET" in getattr(r, "methods", set())}
    known = {
        "/api/cast",
        "/api/difficulty",
        "/api/spy/config",
        "/api/games/{game_id}/events",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
    assert gets == known, f"new GET routes to check for secrets: {gets - known}"
    runner = make_runner(tmp_path)
    monkeypatch.setattr(app_module, "get_spy_runner", lambda: runner)
    app_module.started.clear()
    with TestClient(app_module.app) as c:
        gid = c.post("/api/spy/games", json={"name": "Alex", "role": "spy", "seed": 4}).json()["game_id"]
        place = location(app_module.games[gid].state)
        for path in ("/api/cast", "/api/difficulty", "/openapi.json"):
            body = c.get(path).text.lower()
            assert place not in body or path == "/openapi.json" and place not in body
        config = c.get("/api/spy/config").json()
        assert place in config["places"]  # the whole pool, the same for every game: not a secret
        assert not any(k in json.dumps(config) for k in ("secret", "spy_id", 'location"'))
        app_module.games[gid].task.cancel()
