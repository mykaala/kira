"""Drives one game: asks the engine what is pending, schedules model calls (night and
votes in parallel, discussion one speaker at a time), and streams the human's view out."""

import asyncio
import random
import time
import uuid
from collections import Counter
from collections.abc import Callable

from agents import checks
from agents.costlog import CostLog
from agents.personas import BY_ID, CAST, Persona, Traits, for_game
from agents.runner import AgentRunner, ModelUnavailable
from agents.schemas import BeliefState
from engine import engine
from engine.engine import IllegalMove, Request, mode_of
from engine.views import build_view

CALL_TYPE = {"discussion": "discussion", "vote": "vote", "night": "night"}

Printer = Callable[[str, dict], None]


class Game:
    def __init__(
        self,
        *,
        runner: AgentRunner,
        log: CostLog,
        opponents: int,
        human_name: str | None,
        seed: int | None = None,
        pause_s: float = 0.0,
        turn_timeout_s: float = 60.0,
        auto: bool | None = None,
        printer: Printer | None = None,
        cast_ids: list[str] | None = None,
        traits: dict[str, Traits] | None = None,
        difficulty: str = "tricky",
        extra_roles: tuple[str, ...] = (),
    ):
        self.id = uuid.uuid4().hex[:10]
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        cast = list(CAST)
        random.Random(self.seed).shuffle(cast)
        if cast_ids:  # chosen in the lobby; otherwise a random table
            chosen = [BY_ID[c] for c in cast_ids]
            cast = chosen + [p for p in cast if p not in chosen]
            opponents = len(chosen)
        names = [p.name for p in cast[:opponents]]
        human_index = None
        if human_name:
            human_index = random.Random(self.seed + 1).randrange(opponents + 1)
            names.insert(human_index, human_name)
        else:
            names.append(cast[opponents].name)  # self-play: one more AI in the human's seat

        self.state = engine.new_game(engine.MODES["mafia"], names, human_index, self.seed, extra_roles)
        self.house = {"difficulty": difficulty, "roles": sorted(extra_roles)}
        self.mode = mode_of(self.state)
        self.human = f"p{human_index}" if human_index is not None else None
        by_name = {p.name: p for p in CAST}
        traits = traits or {}
        self.personas: dict[str, Persona] = {
            p.id: for_game(by_name[p.name], difficulty, traits.get(by_name[p.name].id))
            for p in self.state.players
            if not p.is_human
        }
        self.beliefs: dict[str, BeliefState] = {pid: BeliefState() for pid in self.personas}
        self.phrase_uses: Counter = Counter()  # capped stock phrases, across the whole table
        self.phrase_cap = runner.settings.phrase_cap

        self.runner, self.log, self.pause_s, self.printer = runner, log, pause_s, printer
        self.turn_timeout_s = turn_timeout_s
        self.human_spoke = asyncio.Event()
        # manual pace: each AI message is generated only when the human asks for the next one
        self.auto = auto if auto is not None else self.human is None
        self.advance = asyncio.Event()
        self.waiting_next = False
        self.subscribers: list[asyncio.Queue] = []
        self.history: list[tuple[str, dict]] = []  # everything broadcast except live deltas
        self.status: dict | None = None
        self.sent = 0  # engine events already published
        self.human_acted = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.aborted: str | None = None  # why the game stopped early, if it did

        log.game_started(
            self.id,
            self.mode.name,
            self.seed,
            [{"id": p.id, "name": p.name, "role": p.role, "human": p.is_human} for p in self.state.players],
            human=self.human is not None,
        )

    # --- streaming out -------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for item in self.history:
            q.put_nowait(item)
        if self.status:
            q.put_nowait(("status", self.status))
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)

    def _send(self, kind: str, data: dict, keep: bool = True) -> None:
        if keep:
            self.history.append((kind, data))
        for q in self.subscribers:
            q.put_nowait((kind, data))

    def publish(self) -> None:
        """Send the engine events the viewer may see, and a fresh status, from the human's view only."""
        if self.printer:
            for e in self.state.events[self.sent :]:
                self.printer("event", e.model_dump())
            self.sent = len(self.state.events)
            return
        view = build_view(self.mode, self.state, self.human)
        for e in view.events:
            if e.seq >= self.sent:
                self._send("event", e.model_dump())
        self.sent = len(self.state.events)
        self.status = view.model_dump(exclude={"events", "rules"})
        self.status["waiting_on_you"] = any(r.pid == self.human for r in engine.pending(self.state))
        self.status["characters"] = {pid: p.id for pid, p in self.personas.items()}
        self.status["house"] = self.house
        self.status["auto"] = self.auto
        self.status["waiting_for_next"] = self.waiting_next
        self.status["next_speaker"] = self.state.queue[0] if self.waiting_next and self.state.queue else None
        self.status["turns_left"], self.status["turns_total"] = engine.turns_left(self.state)
        for q in self.subscribers:
            q.put_nowait(("status", self.status))

    # --- the human's moves ---------------------------------------------------------

    def used_up(self) -> list[str]:
        return sorted(p for p, n in self.phrase_uses.items() if n >= self.phrase_cap)

    def human_say(self, text: str, accuses: str | None = None) -> None:
        engine.submit_say(self.state, self.human, text[:400], accuses=accuses)
        self.phrase_uses.update(checks.capped_uses(text))
        self.human_spoke.set()
        self.advance.set()  # speaking up also moves the chat on, so someone answers
        self.publish()

    def call_vote(self) -> None:
        engine.call_vote(self.state)
        self.advance.set()  # the loop may be waiting on "next"
        self.human_spoke.set()  # or on the human's own turn
        self.publish()

    def next_message(self) -> None:
        self.advance.set()

    def set_auto(self, auto: bool) -> None:
        self.auto = auto
        if auto:
            self.advance.set()
        self.publish()

    def human_pass(self) -> None:
        if not (self.state.queue and self.state.queue[0] == self.human):
            raise IllegalMove("it is not your turn to speak")
        engine.submit_say(self.state, self.human, "")
        self.human_spoke.set()
        self.publish()

    def human_act(self, action: str) -> None:
        if not any(r.pid == self.human for r in engine.pending(self.state)):
            raise IllegalMove("nothing to do right now")
        engine.submit_action(self.state, self.human, action)
        self.human_acted.set()
        self.publish()

    # --- the loop --------------------------------------------------------------------

    async def run(self) -> None:
        self.publish()
        try:
            while reqs := engine.pending(self.state):
                if reqs[0].kind == "speak" and reqs[0].pid == self.human:
                    await self._human_turn()
                elif reqs[0].kind == "speak":
                    if not self.auto:
                        await self._wait_for_next()
                        now = engine.pending(self.state)
                        if not now or now[0].pid != reqs[0].pid:
                            continue  # the human's message changed who is up
                    await self._speak(reqs[0].pid)
                    if self.auto and self.pause_s:
                        await asyncio.sleep(self.pause_s)
                else:
                    await self._simultaneous(reqs)
                self.publish()
        except ModelUnavailable as e:
            # don't play on with default moves: that would be a fake game
            self.aborted = str(e)
            self._send(
                "error",
                {
                    "message": "Lost the connection to the AI service, so this game can't continue. "
                    "Check your internet connection and start a new game."
                },
            )
        else:
            if self.state.winner and not self.printer:
                # the game is over, so every secret can be shown for review
                self._send("reveal", {"events": [e.model_dump() for e in self.state.events]})
        finally:
            self.log.game_ended(self.id, self.state.winner, self.state.day)

    async def _wait_for_next(self) -> None:
        self.advance.clear()
        self.waiting_next = True
        self.publish()
        try:
            await self.advance.wait()
        finally:
            self.waiting_next = False
            self.publish()  # so the Next button goes away as soon as it's pressed

    def _default(self, pid: str, legal: list[str]) -> str:
        if not legal:
            return "none"
        return self.mode.default_action(self.state, self.state.player(pid), legal, self.state.rng(f"default:{pid}"))

    async def _human_turn(self) -> None:
        """Wait for the human to speak or pass; on timeout their turn is skipped."""
        self.human_spoke.clear()
        self.publish()
        try:
            await asyncio.wait_for(self.human_spoke.wait(), self.turn_timeout_s)
        except TimeoutError:
            if self.state.queue and self.state.queue[0] == self.human:
                engine.submit_say(self.state, self.human, "")

    async def _speak(self, pid: str) -> None:
        view = build_view(self.mode, self.state, pid)
        self._send("typing", {"pid": pid}, keep=False)

        async def delta(text: str) -> None:
            self._send("delta", {"pid": pid, "text": text}, keep=False)

        async def retract() -> None:
            self._send("retract", {"pid": pid}, keep=False)

        result = await self.runner.play(
            game_id=self.id,
            view=view,
            persona=self.personas[pid],
            beliefs=self.beliefs[pid],
            call_type="discussion",
            default_action="none",
            on_delta=delta,
            on_retract=retract,
            claim_roles=self.mode.claimable_roles,
            judge_claim=lambda c: engine.claim_error(self.state, pid, c),
            used_up=self.used_up(),
        )
        self.beliefs[pid] = result.beliefs
        if not result.say:
            self._send("retract", {"pid": pid}, keep=False)
        # the human may have spoken or called the vote meanwhile; this speaker keeps their slot either way
        if self.state.phase == "discussion" and self.state.queue and self.state.queue[0] == pid:
            try:
                engine.submit_say(self.state, pid, result.say, result.claim, result.accuses)
            except IllegalMove:  # the state moved on since the claim or accusation was checked
                engine.submit_say(self.state, pid, result.say)
            self.phrase_uses.update(checks.capped_uses(result.say))

    async def _simultaneous(self, reqs: list[Request]) -> None:
        phase, day = self.state.phase, self.state.day
        ai = [r for r in reqs if r.pid != self.human]
        human_waiting = any(r.pid == self.human for r in reqs)
        self.human_acted.clear()

        # one legal action means no model call
        for r in [r for r in ai if len(r.legal) == 1]:
            engine.submit_action(self.state, r.pid, r.legal[0])
        ai = [r for r in ai if len(r.legal) > 1]

        async def act(r: Request) -> None:
            result = await self.runner.play(
                game_id=self.id,
                view=build_view(self.mode, self.state, r.pid),
                persona=self.personas[r.pid],
                beliefs=self.beliefs[r.pid],
                call_type=CALL_TYPE[phase],
                default_action=self._default(r.pid, r.legal),
            )
            self.beliefs[r.pid] = result.beliefs
            self._send("acted", {"pid": r.pid}, keep=False)  # who is in, never what they chose
            try:
                engine.submit_action(self.state, r.pid, result.action)
            except IllegalMove:
                engine.submit_action(self.state, r.pid, self._default(r.pid, r.legal))

        start = time.perf_counter()
        results = await asyncio.gather(*(act(r) for r in ai), return_exceptions=True)
        for res in results:
            if isinstance(res, BaseException):
                raise res
        if ai:
            self.log.round(self.id, day, phase, len(ai), (time.perf_counter() - start) * 1000)
        if human_waiting and self.state.phase == phase and self.state.day == day:
            self.publish()  # tell the UI it is waiting on the human
            await self.human_acted.wait()
