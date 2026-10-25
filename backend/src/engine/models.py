"""Game state. Every fact about a game lives here, never in a prompt."""

import random
from enum import StrEnum

from pydantic import BaseModel, Field

ABSTAIN = "abstain"
PUBLIC = "public"


def channel(name: str) -> str:
    return f"channel:{name}"


def private(pid: str) -> str:
    return f"private:{pid}"


class PhaseType(StrEnum):
    SEQUENTIAL = "sequential"
    SIMULTANEOUS = "simultaneous"
    AUTOMATIC = "automatic"


class Player(BaseModel):
    id: str
    name: str
    is_human: bool = False
    role: str = ""
    alive: bool = True


class Event(BaseModel):
    seq: int
    day: int
    phase: str
    kind: str  # phase, say, vote, death, elimination, result, game_over, ...
    text: str
    vis: str = PUBLIC  # public | channel:<name> | private:<pid>
    actor: str | None = None
    target: str | None = None


class NewEvent(BaseModel):
    """An event a resolver wants appended; the engine stamps seq/day/phase."""

    kind: str
    text: str
    vis: str = PUBLIC
    actor: str | None = None
    target: str | None = None


class ClaimIn(BaseModel):
    """A role claim attached to a message: "I'm the detective, I checked Kofi: mafia"."""

    role: str
    target: str | None = None  # player id, for a detective result
    result: str | None = None  # "mafia" | "not mafia"


class PublicClaim(ClaimIn):
    seq: int  # the say event that made it
    day: int
    actor: str


class Claim(PublicClaim):
    """The engine's record of a claim. Whether it is true never leaves the engine."""

    true: bool

    def public(self) -> PublicClaim:
        return PublicClaim(**self.model_dump(exclude={"true"}))


class Outcome(BaseModel):
    events: list[NewEvent] = Field(default_factory=list)
    deaths: list[str] = Field(default_factory=list)


class GameState(BaseModel):
    mode: str
    seed: int
    players: list[Player]
    day: int = 0
    phase: str = ""
    round: int = 0
    queue: list[str] = Field(default_factory=list)  # sequential phase: speakers still to go
    submitted: dict[str, str] = Field(default_factory=dict)  # simultaneous phase: pid -> action
    submitted_text: dict[str, str] = Field(default_factory=dict)  # simultaneous phase: pid -> words with the action
    events: list[Event] = Field(default_factory=list)
    winner: str | None = None
    last_deaths: list[str] = Field(default_factory=list)  # deaths from the phase that just ended
    claims: list[Claim] = Field(default_factory=list)  # public role claims, each marked true or false
    accusations: dict[str, str] = Field(default_factory=dict)  # public: player id -> who they accuse now
    options: dict = Field(default_factory=dict)  # this game's own mode switches, over the mode's (Out of Place)

    def player(self, pid: str) -> Player:
        for p in self.players:
            if p.id == pid:
                return p
        raise KeyError(pid)

    def alive(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def rng(self, salt: str = "") -> random.Random:
        """Seeded from state, so the same state always draws the same numbers."""
        return random.Random(f"{self.seed}:{self.day}:{self.phase}:{self.round}:{len(self.events)}:{salt}")
