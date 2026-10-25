"""Drives one hidden-location game headless: asks the engine what is pending and makes the model calls
(ask and answer one at a time, votes in parallel). The human's seat holds another AI or a random bot."""

import asyncio
import random
import time
import uuid
from collections import Counter

from agents.costlog import CostLog
from agents.personas import CAST, Persona, for_game
from agents.runner import ModelUnavailable
from agents.spy_runner import SpyRunner, guess_action
from engine import engine
from engine.engine import IllegalMove, Request
from engine.modes.spy_location import ANSWER, GUESS, SPY_MODE
from engine.views import build_view

BOT_NAME = "Sam"


class SpyGame:
    def __init__(
        self,
        *,
        runner: SpyRunner,
        log: CostLog,
        players: int,
        human_seat: str = "ai",  # "ai": one more AI; "bot": random legal moves and stock lines
        seed: int | None = None,
        difficulty: str = "tricky",
    ):
        self.id = uuid.uuid4().hex[:10]
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        cast = list(CAST)
        random.Random(self.seed).shuffle(cast)
        names = [p.name for p in cast[:players]]
        human_index = None
        if human_seat == "bot":
            human_index = random.Random(self.seed + 1).randrange(players)
            names[human_index] = BOT_NAME
        self.state = engine.new_game(SPY_MODE, names, human_index, self.seed)
        by_name = {p.name: p for p in CAST}
        self.personas: dict[str, Persona] = {
            p.id: for_game(by_name[p.name], difficulty) for p in self.state.players if not p.is_human
        }
        self.bot = random.Random(f"{self.seed}:bot")
        self.runner, self.log = runner, log
        self.defaulted: Counter = Counter()  # call type -> turns that fell back to the default move
        self.leaked_first: Counter = Counter()  # call type -> civilian turns whose first attempt named the location
        self.guess_windows = 0  # spy ask turns that offered a guess
        self.aborted: str | None = None
        log.game_started(
            self.id,
            SPY_MODE.name,
            self.seed,
            [{"id": p.id, "name": p.name, "role": p.role, "human": p.is_human} for p in self.state.players],
            human=human_index is not None,
        )

    async def run(self) -> None:
        try:
            while reqs := engine.pending(self.state):
                if self.state.phase == "vote":
                    await self._vote(reqs)
                else:
                    await self._turn(reqs[0])
        except ModelUnavailable as e:
            self.aborted = str(e)  # don't play on with default moves: that would be a fake game
        finally:
            self.log.game_ended(self.id, self.state.winner, self.state.day)

    def _default(self, r: Request) -> str:
        p = self.state.player(r.pid)
        return SPY_MODE.default_action(self.state, p, r.legal, self.state.rng(f"default:{r.pid}"))

    async def _call(self, r: Request, call_type: str):
        view = build_view(SPY_MODE, self.state, r.pid)
        turn = await self.runner.play(game_id=self.id, view=view, persona=self.personas[r.pid], call_type=call_type)
        if turn.defaulted:
            self.defaulted[call_type] += 1
        if turn.leaked_first and view.role != "spy":
            self.leaked_first[call_type] += 1
        return turn.move

    async def _turn(self, r: Request) -> None:
        phase, player = self.state.phase, self.state.player(r.pid)
        if player.is_human:
            return self._bot_move(r)
        if phase == "ask":
            plan = (build_view(SPY_MODE, self.state, r.pid).intent or {}).get("plan")
            if plan == "guess_window":
                self.guess_windows += 1
                move = await self._call(r, "spy_guess")
                if move and move["location"]:
                    return engine.submit_action(self.state, r.pid, guess_action(move["location"]))
            move = await self._call(r, "ask")
            if move:
                return engine.submit_action(self.state, r.pid, move["target"], text=move["text"])
            return engine.submit_action(self.state, r.pid, self._default(r))
        if phase == "answer":
            move = await self._call(r, "answer")
            return engine.submit_action(self.state, r.pid, ANSWER, text=move["text"] if move else "")
        if phase == "last_chance":
            move = await self._call(r, "last_chance")
            action = guess_action(move["location"]) if move and move["location"] else self._default(r)
            return engine.submit_action(self.state, r.pid, action)
        raise IllegalMove(f"no turn handler for {phase}")

    def _bot_move(self, r: Request) -> None:
        """The human's seat as a bot: never names the location early, stock lines, random legal choices."""
        plain = [a for a in r.legal if not a.startswith(GUESS)]
        engine.submit_action(self.state, r.pid, self.bot.choice(plain or r.legal))

    async def _vote(self, reqs: list[Request]) -> None:
        start = time.perf_counter()
        ai = [r for r in reqs if not self.state.player(r.pid).is_human]
        moves = await asyncio.gather(*(self._call(r, "vote") for r in ai))
        for r, move in zip(ai, moves):
            engine.submit_action(self.state, r.pid, move["target"] if move else self._default(r))
        for r in reqs:
            if self.state.player(r.pid).is_human and self.state.phase == "vote":
                self._bot_move(r)
        self.log.round(self.id, self.state.day, "vote", len(ai), (time.perf_counter() - start) * 1000)
