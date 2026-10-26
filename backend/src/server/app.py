"""HTTP API. The OpenAI key never leaves this process; the browser only sees the human's view."""

import asyncio
import json
import time
from collections import defaultdict

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from agents.personas import BY_ID, CAST, DIFFICULTY, Traits
from engine.engine import IllegalMove

from engine.modes.spy_location import LOCATION_NAMES, SPY_MODE, TITLE

from .deps import get_runner, get_spy_runner
from .orchestrator import Game
from .settings import get_settings
from .spy_live import LeakWarning, SpyLive

app = FastAPI(title="Kira")
games: dict[str, Game | SpyLive] = {}
started: dict[str, list[float]] = defaultdict(list)  # ip -> game start times


class NewGame(BaseModel):
    opponents: int = Field(6, ge=4, le=8)
    name: str = Field("Alex", min_length=1, max_length=20)
    seed: int | None = None
    auto: bool = False  # False: each AI message waits for the player's "next"
    # house rules; anything left out is dealt at random
    cast: list[str] | None = None  # character ids, one per AI seat
    traits: dict[str, Traits] | None = None  # knob overrides by character id
    difficulty: Literal["cozy", "tricky", "merciless"] = "tricky"
    roles: list[Literal["jester", "bodyguard"]] = []

    @model_validator(mode="after")
    def _check(self):
        if self.cast is not None:
            if not 4 <= len(self.cast) <= 8 or len(set(self.cast)) != len(self.cast):
                raise ValueError("cast must be 4 to 8 different characters")
            if unknown := [c for c in self.cast if c not in BY_ID]:
                raise ValueError(f"unknown characters: {unknown}")
            self.opponents = len(self.cast)
        if self.traits and (unknown := [c for c in self.traits if c not in BY_ID]):
            raise ValueError(f"unknown characters: {unknown}")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("each optional role can be added once")
        return self


class Pace(BaseModel):
    auto: bool


class Say(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    accuses: str | None = None  # a player id: the public "you -> them" chip


class Act(BaseModel):
    action: str


def _game(game_id: str) -> Game | SpyLive:
    if game_id not in games:
        raise HTTPException(404, "no such game")
    return games[game_id]


def _mafia(game_id: str) -> Game:
    game = _game(game_id)
    if not isinstance(game, Game):
        raise HTTPException(400, "that isn't a Mafia game")
    return game


def _spy(game_id: str) -> SpyLive:
    game = _game(game_id)
    if not isinstance(game, SpyLive):
        raise HTTPException(400, f"that isn't an {TITLE} game")
    return game


def _rate_limit(request: Request) -> None:
    settings = get_settings()
    ip = request.client.host if request.client else "?"
    recent = [t for t in started[ip] if t > time.time() - 3600]
    if len(recent) >= settings.max_games_per_ip_per_hour:
        raise HTTPException(429, "too many games this hour")
    started[ip] = recent + [time.time()]


@app.get("/api/cast")
async def cast():
    """The characters, for the lobby and portraits. Persona prompt text stays on the server."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "full_name": p.full_name,
            "voice": p.voice,
            "quote": p.quote,
            "traits": p.traits.model_dump(),
        }
        for p in CAST
    ]


@app.get("/api/difficulty")
async def difficulty():
    """How each difficulty shifts the knobs, so the lobby can show the result."""
    return {name: {"suspicious": sus, "liar": liar} for name, (sus, liar, _) in DIFFICULTY.items()}


@app.post("/api/games")
async def create_game(body: NewGame, request: Request):
    settings = get_settings()
    ip = request.client.host if request.client else "?"
    recent = [t for t in started[ip] if t > time.time() - 3600]
    if len(recent) >= settings.max_games_per_ip_per_hour:
        raise HTTPException(429, "too many games this hour")
    started[ip] = recent + [time.time()]

    runner = get_runner()
    taken = {body.name.strip().lower()} & {p.name.lower() for p in CAST}
    if taken:
        raise HTTPException(400, "that name belongs to an AI player; pick another")
    try:
        game = Game(
            runner=runner,
            log=runner.log,
            opponents=body.opponents,
            human_name=body.name.strip(),
            seed=body.seed,
            pause_s=settings.discussion_pause_s,
            turn_timeout_s=settings.human_turn_timeout_s,
            auto=body.auto,
            cast_ids=body.cast,
            traits=body.traits,
            difficulty=body.difficulty,
            extra_roles=tuple(body.roles),
        )
    except ValueError as e:  # e.g. too few villagers for the optional roles
        raise HTTPException(400, str(e))
    games[game.id] = game
    game.task = asyncio.create_task(game.run())
    return {"game_id": game.id, "you": game.human}


@app.get("/api/games/{game_id}/events")
async def events(game_id: str, request: Request):
    game = _game(game_id)
    q = game.subscribe()

    async def stream():
        try:
            while not await request.is_disconnected():
                try:
                    kind, data = await asyncio.wait_for(q.get(), timeout=15)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"event: {kind}\ndata: {json.dumps(data)}\n\n"
        finally:
            game.unsubscribe(q)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/api/games/{game_id}/say")
async def say(game_id: str, body: Say):
    try:
        _mafia(game_id).human_say(body.text, body.accuses)
    except IllegalMove as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/games/{game_id}/call-vote")
async def call_vote(game_id: str):
    try:
        _mafia(game_id).call_vote()
    except IllegalMove as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/games/{game_id}/next")
async def next_message(game_id: str):
    _game(game_id).next_message()
    return {"ok": True}


@app.post("/api/games/{game_id}/pace")
async def pace(game_id: str, body: Pace):
    _game(game_id).set_auto(body.auto)
    return {"ok": True}


@app.post("/api/games/{game_id}/pass")
async def pass_turn(game_id: str):
    try:
        _mafia(game_id).human_pass()
    except IllegalMove as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/games/{game_id}/action")
async def act(game_id: str, body: Act):
    try:
        _mafia(game_id).human_act(body.action)
    except IllegalMove as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# --- Out of Place -------------------------------------------------------------------------------


class NewSpyGame(BaseModel):
    name: str = Field("Alex", min_length=1, max_length=20)
    players: int = Field(6, ge=SPY_MODE.min_players, le=SPY_MODE.max_players)  # the person included
    role: Literal["random", "spy", "civilian"] = "random"
    cast: list[str] | None = None  # character ids for the AI seats; otherwise a random table
    seed: int | None = None
    auto: bool = True
    roles: bool = True  # the lobby's Advanced switches: civilians get a secret role at the place
    ask_angle: bool = False  # each AI ask turn gets a seeded topic

    @model_validator(mode="after")
    def _check(self):
        if self.cast is not None:
            if len(self.cast) != self.players - 1 or len(set(self.cast)) != len(self.cast):
                raise ValueError(f"pick {self.players - 1} different characters")
            if unknown := [c for c in self.cast if c not in BY_ID]:
                raise ValueError(f"unknown characters: {unknown}")
        return self


class SpyMove(BaseModel):
    type: Literal["ask", "answer", "vote", "guess"]
    target: str | None = None  # a player id: who you ask, or who you vote for
    text: str | None = Field(None, max_length=1000)  # cleaned and capped on the server
    confirm: bool = False  # send it even though it names the place


@app.get("/api/spy/config")
async def spy_config():
    """What the lobby and the human spy's places list need. The list isn't a secret: every game draws from it."""
    o = SPY_MODE.options
    return {
        "title": TITLE,
        "min_players": SPY_MODE.min_players,
        "max_players": SPY_MODE.max_players,
        "places": LOCATION_NAMES,
        "options": {
            k: o[k]
            for k in (
                "asks_per_player",
                "spy_survive_votes",
                "tie_revote",
                "last_chance_guess",
                "last_chance_result",
                "roles",
                "ask_angle",
            )
        },
    }


@app.post("/api/spy/games")
async def create_spy_game(body: NewSpyGame, request: Request):
    _rate_limit(request)
    settings = get_settings()
    if body.name.strip().lower() in {p.name.lower() for p in CAST}:
        raise HTTPException(400, "that name belongs to an AI player; pick another")
    runner = get_spy_runner()
    game = SpyLive(
        runner=runner,
        log=runner.log,
        players=body.players,
        human_name=body.name.strip(),
        human_role=body.role,
        cast_ids=body.cast,
        seed=body.seed,
        pause_s=settings.discussion_pause_s,
        auto=body.auto,
        idle_timeout_s=settings.spy_idle_timeout_s,
        options={"roles": body.roles, "ask_angle": body.ask_angle},
    )
    games[game.id] = game
    game.task = asyncio.create_task(game.run())
    return {"game_id": game.id, "you": game.human}


@app.post("/api/spy/games/{game_id}/move")
async def spy_move(game_id: str, body: SpyMove):
    try:
        _spy(game_id).submit(body.model_dump())
    except LeakWarning as w:
        raise HTTPException(409, {"warning": str(w), "word": w.word})
    except IllegalMove as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/spy/games/{game_id}/skip")
async def spy_skip(game_id: str):
    """A person voted out skips ahead to the results."""
    try:
        _spy(game_id).skip()
    except IllegalMove as e:
        raise HTTPException(400, str(e))
    return {"ok": True}
