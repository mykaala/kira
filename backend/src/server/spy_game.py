"""Drives one hidden-location game: asks the engine what is pending and makes the model calls (ask and answer
one at a time, votes in parallel). Headless for self-play, where the human's seat holds another AI or a random
bot; SpyLive (spy_live.py) fills the hooks below to seat a real person."""

import asyncio
import logging
import random
import time
import uuid
from collections import Counter

from agents.costlog import CostLog
from agents.personas import BY_ID, CAST, Persona, for_game
from agents.runner import ModelUnavailable
from agents.spy_runner import SpyRunner, SpyTurn
from engine import engine
from engine.engine import IllegalMove, Request
from engine.models import private
from engine.modes.spy_location import (
    ANSWER,
    CIVILIAN,
    GUESS,
    GUESS_MISS,
    PLACE_ROLE,
    SPY_MODE,
    generic_shortfall,
    location,
)
from engine.views import build_view

BOT_NAME = "Sam"
logger = logging.getLogger("kira.spy")


class SpyGame:
    def __init__(
        self,
        *,
        runner: SpyRunner,
        log: CostLog,
        players: int,
        human_seat: str = "ai",  # "ai": one more AI; "bot": random legal moves and stock lines; "human"
        seed: int | None = None,
        difficulty: str = "tricky",
        human_name: str | None = None,  # human_seat="human": the person's name
        human_role: str = "random",  # human_seat="human": "random", "spy" or "civilian"
        cast_ids: list[str] | None = None,  # the AI seats, chosen in the lobby; otherwise a random table
        options: dict | None = None,  # this game's own switches (e.g. roles, ask_angle) over the mode's
    ):
        self.id = uuid.uuid4().hex[:10]
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        cast = list(CAST)
        random.Random(self.seed).shuffle(cast)
        if cast_ids:
            chosen = [BY_ID[c] for c in cast_ids]
            cast = chosen + [p for p in cast if p not in chosen]
        names = [p.name for p in cast[:players]]
        human_index = None
        if human_seat in ("bot", "human"):
            human_index = random.Random(self.seed + 1).randrange(players)
            if human_seat == "bot":
                names[human_index] = BOT_NAME
            else:  # the AIs keep their seats in order; the person sits among them
                names = names[: players - 1]
                names.insert(human_index, human_name)
        # every switch is fixed for the game when it starts, so a later configure() can't change it mid-game
        self.options = SPY_MODE.options | (options or {})
        self.state = engine.new_game(SPY_MODE, names, human_index, self.seed, options=self.options)
        self.role_shortfall = 0  # roles on: generic roles short of the floor at this place (all it had were used)
        if self.options.get("roles"):
            civilians = sum(p.role == CIVILIAN for p in self.state.players)
            floor = self.options["min_generic_roles_per_game"]
            if short := generic_shortfall(location(self.state), civilians, floor):
                self.role_shortfall = short
                logger.warning(
                    "%s has %d generic roles fewer than min_generic_roles_per_game=%d; dealt all it has",
                    location(self.state), short, floor,
                )  # fmt: skip
        if human_index is not None and human_role in ("spy", "civilian"):
            self._seat_role(self.state.players[human_index], human_role)
        by_name = {p.name: p for p in CAST}
        self.personas: dict[str, Persona] = {
            p.id: for_game(by_name[p.name], difficulty) for p in self.state.players if not p.is_human
        }
        self.bot = random.Random(f"{self.seed}:bot")
        self.runner, self.log = runner, log
        self.defaulted: Counter = Counter()  # call type -> turns that fell back to the default move
        self.leaked_first: Counter = Counter()  # call type -> civilian turns whose first attempt named the location
        self.giveaway_first: Counter = Counter()  # call type -> civilian turns whose first attempt used a giveaway
        self.title_first: Counter = Counter()  # call type -> civilian turns whose first attempt said their role title
        self.guess_windows = 0  # spy ask turns that offered a guess
        self.guesses: list[dict] = []  # every free-text guess with the server's ruling and the rule that made it
        self.empty: Counter = Counter()  # call type -> guess calls that came back empty twice (a pass)
        self.aborted: str | None = None
        self.void: str | None = None  # the game can't be decided fairly (an empty last chance); not counted
        log.game_started(
            self.id,
            SPY_MODE.name,
            self.seed,
            [{"id": p.id, "name": p.name, "role": p.role, "human": p.is_human} for p in self.state.players],
            human=human_index is not None,
        )

    def _seat_role(self, human, role: str) -> None:
        """Give the person the role they asked for by swapping with a seat that has it, right after the deal
        (nothing has used the roles yet: the location reaches civilians by channel, read at view time). The
        swap is always spy for civilian, so the civilian's role at the place moves to the new civilian."""
        if human.role == role:
            return
        holders = [p for p in self.state.players if p.role == role]
        other = holders[random.Random(f"{self.seed}:seat-role").randrange(len(holders))]
        human.role, other.role = other.role, human.role
        civilian = human if human.role == "civilian" else other  # the role card goes with the civilian's seat
        for e in self.state.events:
            if e.kind == PLACE_ROLE:
                if e.target in (human.id, other.id):
                    e.target, e.vis = civilian.id, private(civilian.id)

    async def run(self) -> None:
        try:
            while not self.void and (reqs := engine.pending(self.state)):
                if self.state.phase in ("vote", "revote"):
                    await self._vote(reqs)
                else:
                    await self._turn(reqs[0])
        except ModelUnavailable as e:
            self.aborted = str(e)  # don't play on with default moves: that would be a fake game
        finally:
            self.log.game_ended(self.id, self.state.winner, self.state.day)
            self._finished()

    # --- hooks: headless defaults; SpyLive overrides them ------------------------------------

    async def _human(self, r: Request) -> None:
        """The human seat's move. Headless, it's a bot."""
        self._bot_move(r)

    async def _before_ai(self, r: Request, call_type: str) -> None:
        """Just before an AI's model call (pace, typing indicator)."""

    def _outage(self, r: Request, call_type: str, e: ModelUnavailable) -> None:
        """The model API stayed unreachable. Headless, the game stops: default moves would make it fake."""
        raise e

    def _on_default(self, r: Request, call_type: str) -> None:
        """An AI turn fell back to its default move (timeouts or invalid replies)."""

    def _finished(self) -> None:
        """The game is over (won, drawn, void or aborted)."""

    def _default(self, r: Request) -> str:
        p = self.state.player(r.pid)
        return SPY_MODE.default_action(self.state, p, r.legal, self.state.rng(f"default:{r.pid}"))

    async def _call(self, r: Request, call_type: str):
        await self._before_ai(r, call_type)
        view = build_view(SPY_MODE, self.state, r.pid)
        try:
            turn = await self.runner.play(game_id=self.id, view=view, persona=self.personas[r.pid], call_type=call_type)
        except ModelUnavailable as e:
            self._outage(r, call_type, e)  # raises headless; live, the default move follows (with a notice)
            self.defaulted[call_type] += 1
            self.last_turn = SpyTurn(defaulted=True)
            return None
        if turn.defaulted:
            self.defaulted[call_type] += 1
            self._on_default(r, call_type)
        if turn.leaked_first and view.role != "spy":
            self.leaked_first[call_type] += 1
        if turn.giveaway_first and view.role != "spy":
            self.giveaway_first[call_type] += 1
        if turn.title_first:
            self.title_first[call_type] += 1
        if turn.empty:
            self.empty[call_type] += 1
        self.last_turn = turn
        return turn.move

    async def _rule(self, r: Request, guess: str, kind: str) -> None:
        """The server decides whether the spy's words name the location, then the engine plays the ruling."""
        truth = location(self.state)
        d = await self.runner.matcher.decide(game_id=self.id, guess=guess, truth=truth)
        self.guesses.append(
            {"kind": kind, "exchange": sum(e.kind == "ask" for e in self.state.events), **d.model_dump()}
        )
        engine.submit_action(self.state, r.pid, GUESS + truth if d.match else GUESS_MISS, text=guess)

    async def _turn(self, r: Request) -> None:
        phase, player = self.state.phase, self.state.player(r.pid)
        if player.is_human:
            return await self._human(r)
        if phase == "ask":
            plan = (build_view(SPY_MODE, self.state, r.pid).intent or {}).get("plan")
            if plan == "guess_window":
                self.guess_windows += 1
                move = await self._call(r, "spy_guess")
                if move and move["guess"]:  # empty, null or invalid: a pass, and the spy asks as usual
                    return await self._rule(r, move["guess"], "guess")
            move = await self._call(r, "ask")
            if move:
                return engine.submit_action(self.state, r.pid, move["target"], text=move["text"])
            return engine.submit_action(self.state, r.pid, self._default(r))
        if phase == "answer":
            move = await self._call(r, "answer")
            return engine.submit_action(self.state, r.pid, ANSWER, text=move["text"] if move else "")
        if phase == "last_chance":
            move = await self._call(r, "last_chance")
            if move and move["guess"]:
                return await self._rule(r, move["guess"], "last_guess")
            # never decide a game on a reply that didn't come: empty, invalid twice, or the API down
            self.void = (
                "the spy's last-chance guess came back empty twice"
                if self.last_turn.empty
                else "the spy's last-chance guess never came through"
            )
            return None
        raise IllegalMove(f"no turn handler for {phase}")

    def _bot_move(self, r: Request) -> None:
        """The human's seat as a bot: never names the location early, stock lines, random legal choices."""
        plain = [a for a in r.legal if not a.startswith(GUESS)]
        engine.submit_action(self.state, r.pid, self.bot.choice(plain or r.legal))

    async def _vote(self, reqs: list[Request]) -> None:
        start = time.perf_counter()
        phase = self.state.phase
        ai = [r for r in reqs if not self.state.player(r.pid).is_human]
        for r in [r for r in ai if len(r.legal) == 1]:  # one choice (a tied player in the revote): no model call
            engine.submit_action(self.state, r.pid, r.legal[0])
        ai = [r for r in ai if len(r.legal) > 1]
        human = [r for r in reqs if self.state.player(r.pid).is_human]

        async def ai_votes() -> None:
            moves = await asyncio.gather(*(self._call(r, "vote") for r in ai))
            for r, move in zip(ai, moves):
                engine.submit_action(self.state, r.pid, move["target"] if move else self._default(r))

        # the AIs vote while the person decides; the engine resolves when the last ballot is in
        await asyncio.gather(ai_votes(), *(self._human(r) for r in human))
        self.log.round(self.id, self.state.day, phase, len(ai), (time.perf_counter() - start) * 1000)
