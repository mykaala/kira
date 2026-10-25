"""The game loop as a step machine. No I/O: callers ask what is pending, then submit moves."""

from pydantic import BaseModel

from . import referee
from .config import ModeConfig
from .models import Claim, ClaimIn, Event, GameState, NewEvent, Outcome, PhaseType, Player
from .modes.mafia import MAFIA_MODE
from .speakers import extra_speakers, round_one_order

MODES: dict[str, ModeConfig] = {MAFIA_MODE.name: MAFIA_MODE}


class IllegalMove(Exception):
    pass


class Request(BaseModel):
    pid: str
    phase: str
    kind: str  # "speak" | "act"
    legal: list[str] = []


def mode_of(state: GameState) -> ModeConfig:
    return MODES[state.mode]


def new_game(
    mode: ModeConfig, names: list[str], human_index: int | None, seed: int, extra_roles: tuple[str, ...] = ()
) -> GameState:
    roles = mode.roles_for(len(names), extra_roles)
    players = [Player(id=f"p{i}", name=n, is_human=(i == human_index)) for i, n in enumerate(names)]
    state = GameState(mode=mode.name, seed=seed, players=players)
    state.rng("roles").shuffle(roles)
    for p, role in zip(players, roles):
        p.role = role
    _enter_phase(state, mode.first_phase)
    return state


def pending(state: GameState) -> list[Request]:
    if state.winner:
        return []
    mode = mode_of(state)
    spec = mode.phases[state.phase]
    if spec.type == PhaseType.SEQUENTIAL:
        return [Request(pid=state.queue[0], phase=state.phase, kind="speak")] if state.queue else []
    if spec.type == PhaseType.SIMULTANEOUS:
        return [
            Request(pid=pid, phase=state.phase, kind="act", legal=legal)
            for pid, legal in _actors(state).items()
            if pid not in state.submitted
        ]
    return []


def submit_action(state: GameState, pid: str, action: str) -> None:
    mode = mode_of(state)
    if mode.phases[state.phase].type != PhaseType.SIMULTANEOUS:
        raise IllegalMove(f"no actions during {state.phase}")
    if pid in state.submitted:
        raise IllegalMove(f"{pid} already acted this phase")
    if err := referee.validate(mode, state, pid, action):
        raise IllegalMove(err)
    state.submitted[pid] = action
    if not pending(state):
        _end_phase(state)


def claim_error(state: GameState, pid: str, claim: ClaimIn) -> str | None:
    """Why this claim can't be made (an unknown role, a bad target, or the real detective
    misreporting a result), or None."""
    mode = mode_of(state)
    if claim.role not in mode.claimable_roles:
        return f"you can only claim one of: {', '.join(mode.claimable_roles)}"
    if claim.target is not None and (claim.target == pid or claim.target not in {p.id for p in state.players}):
        return "a claim's target must be another player"
    return mode.judge_claim(state, state.player(pid), claim)[0] if mode.judge_claim else None


def accuse_error(state: GameState, pid: str, target: str) -> str | None:
    if target == pid:
        return "you can't accuse yourself"
    if target not in {p.id for p in state.alive()}:
        return "you can only accuse a living player"
    return None


def submit_say(state: GameState, pid: str, text: str, claim: ClaimIn | None = None, accuses: str | None = None) -> None:
    """A discussion message, optionally carrying a role claim and a public accusation (who the
    speaker is pointing at now). The queued speaker's message (or empty pass) ends their turn.
    Anyone else (the human) may interject: in round 1 that uses up their own slot, so
    nobody speaks twice before everyone has spoken once; in later rounds, whoever is up
    keeps their turn and the speakers after them are re-picked to respond."""
    mode = mode_of(state)
    spec = mode.phases[state.phase]
    player = state.player(pid)
    if spec.type != PhaseType.SEQUENTIAL or not player.alive:
        raise IllegalMove(f"{player.name} cannot speak now")
    text = text.strip()
    if claim and text:
        if err := claim_error(state, pid, claim):
            raise IllegalMove(err)
    if accuses and text:
        if err := accuse_error(state, pid, accuses):
            raise IllegalMove(err)
    if text:
        _emit(state, NewEvent(kind="say", actor=pid, text=text, target=accuses))  # target: the public accusation
        repeat = any(c.actor == pid and ClaimIn(**c.model_dump()) == claim for c in state.claims)
        if claim and not repeat:  # repeating the same claim doesn't add a new one
            true = mode.judge_claim(state, player, claim)[1] if mode.judge_claim else False
            state.claims.append(
                Claim(seq=state.events[-1].seq, day=state.day, actor=pid, true=true, **claim.model_dump())
            )
        if accuses:
            state.accusations[pid] = accuses
    if state.queue and state.queue[0] == pid:
        state.queue.pop(0)
    elif text and pid in state.queue:
        state.queue.remove(pid)
    elif text and state.round > 0 and state.queue:
        head = state.queue[0]
        state.queue = [head] + extra_speakers(state, len(state.queue) - 1, exclude=(head,))
    _advance_sequential(state)


def call_vote(state: GameState) -> None:
    """End the discussion early: the remaining speakers are skipped and the vote opens."""
    if mode_of(state).phases[state.phase].type != PhaseType.SEQUENTIAL or state.winner:
        raise IllegalMove("the vote can only be called during the discussion")
    state.queue = []
    state.round = mode_of(state).phases[state.phase].rounds
    _end_phase(state)


def turns_left(state: GameState) -> tuple[int, int]:
    """(turns left, turns in total) for the current discussion; (0, 0) outside one. Round 1 is
    every living player; later rounds add up to `extra_speakers` AI players each."""
    spec = mode_of(state).phases[state.phase]
    if spec.type != PhaseType.SEQUENTIAL or state.winner:
        return 0, 0
    extras = min(spec.extra_speakers, sum(not p.is_human for p in state.alive()))
    later = spec.rounds - 1 - state.round
    first = len([e for e in state.events if e.kind == "say" and e.day == state.day and e.phase == state.phase])
    left = len(state.queue) + max(0, later) * extras
    return left, first + left


def _actors(state: GameState) -> dict[str, list[str]]:
    mode = mode_of(state)
    return {p.id: legal for p in state.alive() if (legal := mode.legal_actions(state, p))}


def _emit(state: GameState, e: NewEvent) -> None:
    state.events.append(Event(seq=len(state.events), day=state.day, phase=state.phase, **e.model_dump()))


def _enter_phase(state: GameState, name: str) -> None:
    mode = mode_of(state)
    spec = mode.phases[name]
    if name == mode.new_day_phase:
        state.day += 1
        state.accusations = {}
    state.phase, state.round, state.queue, state.submitted = name, 0, [], {}
    _emit(state, NewEvent(kind="phase", text=f"Day {state.day}: {name}"))
    if spec.type == PhaseType.AUTOMATIC:
        _end_phase(state)
    elif spec.type == PhaseType.SEQUENTIAL:
        state.queue = round_one_order(state)
        _advance_sequential(state)
    elif not _actors(state):
        _end_phase(state)


def _advance_sequential(state: GameState) -> None:
    spec = mode_of(state).phases[state.phase]
    while not state.queue:
        state.round += 1
        if state.round >= spec.rounds:
            _end_phase(state)
            return
        state.queue = extra_speakers(state, spec.extra_speakers)


def _end_phase(state: GameState) -> None:
    mode = mode_of(state)
    outcome: Outcome = mode.resolvers[state.phase](state, dict(state.submitted))
    for e in outcome.events:
        _emit(state, e)
    for pid in outcome.deaths:
        state.player(pid).alive = False
    state.last_deaths = list(outcome.deaths)
    if state.phase in mode.clear_accusations_after:
        state.accusations = {}
    alive = {p.id for p in state.alive()}
    state.accusations = {a: t for a, t in state.accusations.items() if a in alive and t in alive}
    if winner := mode.win_check(state):
        state.winner = winner
        roles = ", ".join(f"{p.name} was {p.role}" for p in state.players)
        _emit(state, NewEvent(kind="game_over", target=winner, text=f"The {winner} wins! {roles}."))
        return
    _enter_phase(state, mode.transitions[state.phase])
