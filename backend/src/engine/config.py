"""A game mode is data plus a few pure functions. The engine never changes between modes."""

import random
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from .models import ClaimIn, GameState, Outcome, PhaseType, Player


class PhaseSpec(BaseModel):
    name: str
    type: PhaseType
    rounds: int = 1  # sequential phases only: round 1 is everyone, later rounds are extras
    extra_speakers: int = 3
    timeout_s: float = 10.0


class ModeConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    title: str
    rules: str  # plain-language rules shown to every agent
    rules_roles_hidden: str = ""  # the same rules when roles are not revealed on death
    rules_for: Callable[[GameState], str] | None = None  # rules worded for one game's own switches, if they vary
    min_players: int
    max_players: int
    roles_by_count: dict[int, dict[str, int]]
    optional_roles: list[str] = []  # each one dealt replaces a villager
    teams: dict[str, str]  # role -> team
    channels: dict[str, list[str]]  # channel name -> roles that can read it
    teammates_visible: list[str]  # roles that know each other
    phases: dict[str, PhaseSpec]
    first_phase: str
    new_day_phase: str  # entering this phase starts a new day
    transitions: dict[str, str]  # phase -> next phase (a win check overrides)
    reveal_role_on_death: bool = True
    options: dict[str, Any] = {}  # mode-specific switches, read by the mode's own functions

    legal_actions: Callable[[GameState, Player], list[str]]
    resolvers: dict[str, Callable[[GameState, dict[str, str]], Outcome]]
    default_action: Callable[[GameState, Player, list[str], random.Random], str]
    win_check: Callable[[GameState], str | None]
    claimable_roles: list[str] = []  # roles a player may publicly claim
    clear_accusations_after: list[str] = []  # phases after which public accusations reset (and each new day)
    # (error for an impossible claim or None, whether the claim is true)
    judge_claim: Callable[[GameState, Player, ClaimIn], tuple[str | None, bool]] | None = None
    # a private per-day plan for this player (e.g. the mafia's bluffing intent), or None
    intent: Callable[[GameState, Player], dict | None] | None = None
    # the phase after this one, for modes whose order depends on the game (overrides `transitions`)
    next_phase: Callable[[GameState], str] | None = None
    # moves this player may make out of turn, each ending the current phase at once (see engine.interrupt)
    interrupts: Callable[[GameState, Player], list[str]] | None = None
    # the game-over text from (state, winner, roles); None keeps "The <winner> wins! <roles>." (e.g. for a draw)
    end_text: Callable[[GameState, str, str], str] | None = None

    def roles_for(self, n: int, extras: tuple[str, ...] = ()) -> list[str]:
        if n not in self.roles_by_count:
            raise ValueError(f"{self.name} supports {self.min_players}-{self.max_players} players, got {n}")
        roles = [role for role, count in self.roles_by_count[n].items() for _ in range(count)]
        for extra in extras:
            if extra not in self.optional_roles:
                raise ValueError(f"{self.name} has no optional role {extra!r}")
            if "villager" not in roles:
                raise ValueError(f"not enough villagers to add a {extra} with {n} players")
            roles[roles.index("villager")] = extra
        return roles

    def channels_for(self, role: str) -> list[str]:
        return [name for name, roles in self.channels.items() if role in roles]
