"""Out of Place with a person at the table: the game waits on their turns, streams their view (and only their
view) to the browser, and keeps going through API trouble with default moves and a visible notice."""

import asyncio
import contextlib
import time
from collections import Counter

from agents.personas import BY_ID
from agents.spy_guess import guess_error
from agents.runner import ModelUnavailable
from engine import engine
from engine.engine import IllegalMove, Request
from engine.modes.spy_location import (
    ANSWER,
    CIVILIAN,
    LOCATION_NAMES,
    PLACE_ROLE,
    SPY,
    SPY_MODE,
    TITLE,
    asker,
    answerer,
    exchange_cap,
    location,
    names_title,
    place_role,
    round_asks,
    round_no,
    spy,
    survive_votes,
    tied_players,
    votes_survived,
)
from engine.views import build_view

from .spy_game import SpyGame
from .spy_text import human_text, names_place

TURN_OF_PHASE = {"ask": "ask", "answer": "answer", "vote": "vote", "revote": "revote", "last_chance": "last_chance"}
MOVES_FOR_TURN = {  # the move types each turn takes ("guess" during the questions: the spy only)
    "ask": {"ask", "guess"},
    "answer": {"answer", "guess"},
    "vote": {"vote"},
    "revote": {"vote"},
    "last_chance": {"guess"},
}
PROMPTS = {
    "ask": "Your turn to ask. Pick someone and ask them one question about the place.",
    "answer": "{asker} asked you: {question}",
    "vote": "Everyone has asked. Vote for who you think is the spy.",
    "revote": "The vote tied. Vote again, between the tied players only.",
    "last_chance": "You were caught! Name the place to save a draw.",
}
SPY_ASK_PROMPT = "Your turn to ask, or name the place if you think you know it."
SPY_ANSWER_PROMPT = "{asker} asked you: {question} Answer, or name the place if you think you know it."


# not sent: the location and a civilian's role at it reach them only in their role card (status.secret), and
# the per-turn phase markers carry nothing the screen needs (status says the phase) while each would pause playback
HIDDEN_KINDS = {"location", PLACE_ROLE, "phase"}


class LeakWarning(Exception):
    """A civilian's text names the place (or their own role): a soft warning, sent again with confirm to post it."""

    def __init__(self, word: str, role: bool = False):
        super().__init__(
            f'That says your role ("{word}"), and roles are secret. Send it anyway?'
            if role
            else f'That names the place ("{word}"), which gives it away to the spy. Send it anyway?'
        )
        self.word = word


class SpyLive(SpyGame):
    def __init__(
        self,
        *,
        runner,
        log,
        players: int,
        human_name: str,
        human_role: str = "random",
        cast_ids: list[str] | None = None,
        seed: int | None = None,
        pause_s: float = 0.0,
        auto: bool = True,
        idle_timeout_s: float = 1800.0,
        options: dict | None = None,
    ):
        super().__init__(
            runner=runner,
            log=log,
            players=players,
            human_seat="human",
            seed=seed,
            human_name=human_name,
            human_role=human_role,
            cast_ids=cast_ids,
            options=options,
        )
        self.human = next(p.id for p in self.state.players if p.is_human)
        self.pause_s, self.auto, self.idle_timeout_s = pause_s, auto, idle_timeout_s
        self.subscribers: list[asyncio.Queue] = []
        self.history: list[tuple[str, dict]] = []  # everything sent except passing signals, replayed on connect
        self.status: dict | None = None
        self.sent = 0  # engine events already published
        self.turn: dict | None = None  # the person's pending turn
        self._move: asyncio.Future | None = None
        self._guess: asyncio.Future | None = None  # the person as the spy, while an AI is up: a guess out of turn
        self.advance = asyncio.Event()  # "next", when auto-advance is off
        self.waiting_next = False
        self.notices: list[str] = []
        self.ended: str | None = None  # why the game stopped without a result (idle, no result)
        self.last_active = time.time()
        self.task: asyncio.Task | None = None
        self.reveal: dict | None = None
        self.skipping = False  # a person voted out chose to skip ahead: the AIs play on with no pauses

    # --- streaming out ---------------------------------------------------------------------

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
        """The person's view: new public events and a fresh status. The place reaches a civilian only in the
        status's `secret` (their role card), never as an event."""
        view = build_view(SPY_MODE, self.state, self.human)
        for e in view.events:
            if e.seq >= self.sent and e.kind not in HIDDEN_KINDS:
                self._send("event", e.model_dump())
        self.sent = len(self.state.events)
        self.status = self.status_of(view)
        for q in self.subscribers:
            q.put_nowait(("status", self.status))

    def status_of(self, view) -> dict:
        s = self.state
        ids = {p.id for p in s.players}
        asks = [e for e in s.events if e.kind == "ask"]
        answers = [e for e in s.events if e.kind == "answer"]
        over = bool(s.winner or self.ended or self.void)
        me = s.player(self.human)
        # the spy may name the place at any point during the questions, on anyone's turn
        can_guess = not over and me.role == SPY and me.alive and s.phase in ("ask", "answer")
        turn = None
        if self.turn:
            legal = [a for a in self.turn["legal"] if a in ids]
            turn = {
                "type": self.turn["type"],
                "targets": legal,
                "can_guess": self.turn["type"] in ("ask", "answer") and can_guess,
                "prompt": self.turn["prompt"],
            }
        secret = {"place": location(s)} if view.role == CIVILIAN else {"spy": True}
        if card := place_role(s, self.human):  # roles on: the person's own role card, never anyone else's
            secret["role"] = card
        return {
            "mode": SPY_MODE.name,
            "title": TITLE,
            "you": self.human,
            "role": view.role,
            # a player voted out shows as a civilian (the only role ever shown during a game)
            "players": [{"id": p.id, "name": p.name, "role": p.role, "alive": p.alive} for p in view.players],
            "phase": s.phase,
            "winner": s.winner,
            "over": over,
            "ended": self.ended or self.void,
            "end_text": next((e.text for e in reversed(s.events) if e.kind == "game_over"), None),
            "turn": turn,
            "waiting_on_you": turn is not None,
            "can_guess": can_guess,
            "asker": asker(s) if s.phase == "ask" else None,
            "answerer": answerer(s) if s.phase == "answer" else None,
            "revote_between": tied_players(s) if s.phase == "revote" else [],
            "asked": {pid: sum(e.actor == pid for e in asks) for pid in ids},
            "answered": {pid: sum(e.actor == pid for e in answers) for pid in ids},
            "questions": len(round_asks(s)),  # this round's
            "questions_total": exchange_cap(s),
            "round": round_no(s),
            "votes_survived": votes_survived(s),
            "survive_votes": survive_votes(s),
            "ghost": not s.player(self.human).alive and not over,  # voted out: watching to the end
            "characters": {pid: p.id for pid, p in self.personas.items()},
            "auto": self.auto,
            "waiting_for_next": self.waiting_next,
            "secret": secret,
            "notices": list(self.notices),
            "rules": view.rules,
        }

    def _notice(self, text: str) -> None:
        self.notices.append(text)
        self._send("notice", {"text": text})

    # --- the person's moves --------------------------------------------------------------

    def submit(self, move: dict) -> None:
        """Check a move from the browser and hand it to the waiting game loop. IllegalMove or LeakWarning
        if it can't be played as sent."""
        t = self.turn
        kind = move.get("type")
        if kind == "guess" and not t:
            return self._submit_guess(move)
        if not t or not self._move or self._move.done():
            raise IllegalMove("it isn't your turn")
        if kind not in MOVES_FOR_TURN[t["type"]]:
            raise IllegalMove(f"you can't {kind} now")
        me = self.state.player(self.human)
        out: dict = {"type": kind}
        if kind in ("ask", "vote"):
            if move.get("target") not in t["legal"] or move.get("target") not in {p.id for p in self.state.players}:
                raise IllegalMove("pick one of the highlighted players")
            out["target"] = move["target"]
        if kind in ("ask", "answer", "guess"):
            try:
                out["text"] = human_text(move.get("text") or "")
            except ValueError as e:
                raise IllegalMove(str(e)) from None
        if kind == "guess":
            if me.role != SPY:
                raise IllegalMove("only the spy names the place")
            if err := guess_error(out["text"], allow_null=False):
                raise IllegalMove(err)
        if kind in ("ask", "answer") and me.role == CIVILIAN and not move.get("confirm"):
            if word := names_place(out["text"], location(self.state)):
                raise LeakWarning(word)
            if (card := place_role(self.state, self.human)) and names_title(out["text"], card["title"]):
                raise LeakWarning(card["title"], role=True)
        self.last_active = time.time()
        self._move.set_result(out)

    def _submit_guess(self, move: dict) -> None:
        """The spy names the place while someone else is up: the game loop takes it as soon as it can."""
        s, me = self.state, self.state.player(self.human)
        if me.role != SPY:
            raise IllegalMove("only the spy names the place")
        if s.winner or self.ended or self.void or not me.alive or s.phase not in ("ask", "answer"):
            raise IllegalMove("you can name the place while questions are being asked")
        if self._guess is None:
            self._guess = asyncio.get_running_loop().create_future()
        if self._guess.done():
            raise IllegalMove("you already named the place")
        try:
            text = human_text(move.get("text") or "")
        except ValueError as e:
            raise IllegalMove(str(e)) from None
        if err := guess_error(text, allow_null=False):
            raise IllegalMove(err)
        self.last_active = time.time()
        self._guess.set_result(text)

    def skip(self) -> None:
        """A person who was voted out skips ahead: the rest of the game plays with no pauses."""
        if self.state.player(self.human).alive:
            raise IllegalMove("only a player who is out can skip ahead")
        self.skipping = True
        self.advance.set()

    def next_message(self) -> None:
        self.advance.set()

    def set_auto(self, auto: bool) -> None:
        self.auto = auto
        if auto:
            self.advance.set()
        self.publish()

    # --- hooks -----------------------------------------------------------------------------

    async def run(self) -> None:
        self.publish()
        await super().run()

    async def _human(self, r: Request) -> None:
        kind = TURN_OF_PHASE[self.state.phase]
        players = {p.id for p in self.state.players}
        if kind in ("vote", "revote") and len([a for a in r.legal if a in players]) == 1:
            only = next(a for a in r.legal if a in players)
            self._notice(f"You vote for {self.state.player(only).name}, the only choice.")
            engine.submit_action(self.state, r.pid, only)
            return self.publish()
        prompt = PROMPTS[kind]
        if kind == "answer":
            q = next(e for e in reversed(self.state.events) if e.kind == "ask")
            prompt = prompt.format(asker=self.state.player(q.actor).name, question=q.text)
            if self.state.player(r.pid).role == SPY:
                prompt = SPY_ANSWER_PROMPT.format(asker=self.state.player(q.actor).name, question=q.text)
        elif kind == "ask" and self.state.player(r.pid).role == SPY:
            prompt = SPY_ASK_PROMPT
        self._move = asyncio.get_running_loop().create_future()
        self.turn = {"type": kind, "legal": list(r.legal), "prompt": prompt}
        self.publish()
        self._send("waiting", {"type": kind}, keep=False)
        try:
            move = await asyncio.wait_for(self._move, self.idle_timeout_s)
        except TimeoutError:
            self.turn = None
            self.ended = f"nobody moved for {round(self.idle_timeout_s / 60)} minutes, so the game ended"
            self.void = self.ended
            self._notice(f"The game ended: {self.ended}.")
            return self.publish()
        self.turn = None
        if move["type"] == "guess":
            await self._rule(r, move["text"], "last_guess" if kind == "last_chance" else "guess")
        elif move["type"] == "ask":
            engine.submit_action(self.state, r.pid, move["target"], text=move["text"])
        elif move["type"] == "answer":
            engine.submit_action(self.state, r.pid, ANSWER, text=move["text"])
        else:
            engine.submit_action(self.state, r.pid, move["target"])
        self.publish()

    async def _before_ai(self, r: Request, call_type: str) -> None:
        if call_type == "vote":
            return  # votes run in parallel; they're revealed one by one as events
        if call_type == "spy_guess" and r.pid != asker(self.state):
            return  # an AI spy's window before someone else asks: no pause, and no typing (it would out them)
        if call_type != "spy_guess" and not self.skipping:  # a guess window comes right before its question
            if not self.auto:
                self.advance.clear()
                self.waiting_next = True
                self.publish()
                try:
                    await asyncio.wait_for(self.advance.wait(), self.idle_timeout_s)
                except TimeoutError:
                    pass  # an unattended table plays on; the person's own turns end idle games
                finally:
                    self.waiting_next = False
            elif self.pause_s:
                await asyncio.sleep(self.pause_s)
        self._send("typing", {"pid": r.pid}, keep=False)

    def _outage(self, r: Request, call_type: str, e: ModelUnavailable) -> None:
        name = self.state.player(r.pid).name
        self._notice(f"The AI service didn't answer, so {name} made a default move.")

    def _on_default(self, r: Request, call_type: str) -> None:
        name = self.state.player(r.pid).name
        self._notice(f"{name}'s turn timed out, so they made a default move.")

    async def _vote(self, reqs: list[Request]) -> None:
        await super()._vote(reqs)
        self.publish()

    async def _turn(self, r: Request) -> None:
        me = self.state.player(self.human)
        if r.pid != self.human and me.role == SPY and me.alive and self.state.phase in ("ask", "answer"):
            await self._race(r)
        else:
            await super()._turn(r)
        self.publish()

    async def _race(self, r: Request) -> None:
        """An AI's turn while the person is the spy: a guess from them stops the turn and is played at once."""
        if self._guess is None:  # kept across turns, so a guess sent between two turns still counts
            self._guess = asyncio.get_running_loop().create_future()
        guess, task = self._guess, asyncio.ensure_future(super()._turn(r))
        try:
            await asyncio.wait({task, guess}, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:  # the game itself was stopped
            task.cancel()
            raise
        if not guess.done():
            return await task
        self._guess = None
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        elif task.exception():
            raise task.exception()
        if self.state.winner or self.state.phase not in ("ask", "answer"):
            return self._notice("Too late to name the place: the questions are over.")
        me = Request(pid=self.human, phase=self.state.phase, kind="act")
        await self._rule(me, guess.result(), "guess")

    def _finished(self) -> None:
        s = self.state
        if self.void and not self.ended:
            self.ended = f"no result: {self.void}"
            self._notice(f"No result: {self.void}.")
        self.publish()
        if not (s.winner or self.ended):
            return  # aborted mid-game (headless only)
        starts = [i for i, e in enumerate(s.events) if e.kind == "first"] + [len(s.events)]
        rounds = []
        for a, b in zip(starts, starts[1:]):  # each round's vote, its revote, and who went out
            evs = s.events[a:b]
            if not any(e.kind == "vote" for e in evs):
                continue
            tally = lambda phase: dict(Counter(e.target for e in evs if e.kind == "vote" and e.phase == phase))  # noqa: E731
            out = next((e.target for e in evs if e.kind == "accused" and e.target and e.target != spy(s).id), None)
            rounds.append({"round": len(rounds) + 1, "votes": tally("vote"), "revotes": tally("revote"), "out": out})
        last = rounds[-1] if rounds else {"votes": {}, "revotes": {}}
        self.reveal = {
            "events": [e.model_dump() for e in s.events if e.kind not in HIDDEN_KINDS],
            "roles": {p.id: p.role for p in s.players},
            "place_roles": {p.id: card["title"] for p in s.players if (card := place_role(s, p.id))},
            "place": location(s),
            "spy": spy(s).id,
            "voices": {pid: BY_ID[p.id].voice for pid, p in self.personas.items()},
            "votes": last["votes"],  # the last vote's tally
            "revotes": last["revotes"],
            "rounds": rounds,
            "survive_votes": survive_votes(s),
            "guesses": [
                {k: g[k] for k in ("kind", "guess", "rule", "reason", "match", "exchange")} for g in self.guesses
            ],
            "end_text": next((e.text for e in reversed(s.events) if e.kind == "game_over"), None),
            "winner": s.winner,
            "ended": self.ended,
            "places": LOCATION_NAMES,
            "options": s.options,  # every switch this game ran with
        }
        self._send("reveal", self.reveal)
