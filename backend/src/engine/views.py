"""Per-player views. Agents and the human UI only ever see one of these, so a secret
that is not in the view cannot leak."""

from pydantic import BaseModel

from .config import ModeConfig
from .models import PUBLIC, Event, GameState, PublicClaim, channel, private


class PlayerInfo(BaseModel):
    id: str
    name: str
    alive: bool
    role: str | None = None  # only when this viewer may know it


class PlayerView(BaseModel):
    mode: str
    rules: str
    you: str
    role: str
    team: str
    teammates: list[str]
    players: list[PlayerInfo]
    day: int
    phase: str
    events: list[Event]
    legal_actions: list[str]
    winner: str | None
    roles_revealed_on_death: bool = True
    claims: list[PublicClaim] = []  # every public role claim, never whether it is true
    accusations: dict[str, str] = {}  # public: who each player is accusing right now
    intent: dict | None = None  # this player's own private plan for today, if the mode gives one


def can_see(mode: ModeConfig, state: GameState, viewer: str, e: Event) -> bool:
    role = state.player(viewer).role
    return e.vis == PUBLIC or e.vis == private(viewer) or e.vis in {channel(c) for c in mode.channels_for(role)}


def known_role(mode: ModeConfig, state: GameState, viewer: str, pid: str) -> str | None:
    me, them = state.player(viewer), state.player(pid)
    if viewer == pid or state.winner or (not them.alive and mode.reveal_role_on_death):
        return them.role
    if me.role in mode.teammates_visible and me.role == them.role:
        return them.role
    return None


def build_view(mode: ModeConfig, state: GameState, viewer: str) -> PlayerView:
    me = state.player(viewer)
    teammates = [
        p.id for p in state.players if p.id != viewer and me.role in mode.teammates_visible and p.role == me.role
    ]
    return PlayerView(
        mode=mode.name,
        rules=mode.rules if mode.reveal_role_on_death else (mode.rules_roles_hidden or mode.rules),
        roles_revealed_on_death=mode.reveal_role_on_death,
        you=viewer,
        role=me.role,
        team=mode.teams[me.role],
        teammates=teammates,
        players=[
            PlayerInfo(id=p.id, name=p.name, alive=p.alive, role=known_role(mode, state, viewer, p.id))
            for p in state.players
        ],
        day=state.day,
        phase=state.phase,
        events=[e for e in state.events if can_see(mode, state, viewer, e)],
        legal_actions=mode.legal_actions(state, me),
        winner=state.winner,
        claims=[c.public() for c in state.claims],
        accusations=dict(state.accusations),
        intent=mode.intent(state, me) if mode.intent else None,
    )
