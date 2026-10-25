"""Random bots: play any game to the end with legal moves, no model involved."""

import random

from engine.engine import MODES, claim_error, new_game, pending, submit_action, submit_say
from engine.models import ClaimIn, GameState
from engine.views import build_view

NAMES = ["Ana", "Bo", "Cy", "Dee", "Eli", "Fay", "Gus", "Hal", "Ivy"]


def play_random(
    seed: int,
    n: int = 7,
    human_index: int | None = 0,
    on_step=None,
    max_steps: int = 2000,
    extra_roles: tuple[str, ...] = (),
) -> GameState:
    rng = random.Random(seed)
    state = new_game(MODES["mafia"], NAMES[:n], human_index, seed, extra_roles)
    for _ in range(max_steps):
        reqs = pending(state)
        if not reqs:
            break
        if on_step:
            on_step(state)
        # the human sometimes interjects during discussion
        if (
            reqs[0].kind == "speak"
            and human_index is not None
            and rng.random() < 0.2
            and state.players[human_index].alive
        ):
            submit_say(state, f"p{human_index}", f"I think {rng.choice(NAMES[:n])} is lying.")
            continue
        r = reqs[0]
        if r.kind == "speak":
            target = rng.choice(state.alive()).name
            submit_say(state, r.pid, f"Hmm, {target} seems quiet.", _random_claim(state, r.pid, rng))
        else:
            submit_action(state, r.pid, rng.choice(r.legal))
    return state


def _random_claim(state: GameState, pid: str, rng: random.Random) -> ClaimIn | None:
    """Mafia follow their team plan; anyone else sometimes claims a role, true or not."""
    plan = build_view(MODES["mafia"], state, pid).intent
    if plan and plan.get("claim"):
        return ClaimIn(**plan["claim"])
    if rng.random() > 0.1:
        return None
    others = [p.id for p in state.players if p.id != pid]
    claim = ClaimIn(role=rng.choice(MODES["mafia"].claimable_roles))
    if claim.role == "detective" and rng.random() < 0.7:
        claim.target, claim.result = rng.choice(others), rng.choice(["mafia", "not mafia"])
    return None if claim_error(state, pid, claim) else claim
