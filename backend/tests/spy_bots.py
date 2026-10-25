"""Random bots for the hidden-location game: legal moves and stock lines, no model involved."""

import random

from engine.engine import new_game, pending, submit_action
from engine.models import GameState
from engine.modes.spy_location import GUESS, SPY_MODE

NAMES = ["Ana", "Bo", "Cy", "Dee", "Eli", "Fay", "Gus", "Hal"]


def play_spy(seed: int, n: int = 6, on_step=None, guess_rate: float = 0.1, max_steps: int = 500) -> GameState:
    rng = random.Random(seed)
    state = new_game(SPY_MODE, NAMES[:n], 0, seed)
    for _ in range(max_steps):
        reqs = pending(state)
        if not reqs:
            break
        if on_step:
            on_step(state)
        r = reqs[0]
        plain = [a for a in r.legal if not a.startswith(GUESS)]
        guesses = [a for a in r.legal if a.startswith(GUESS)]
        action = rng.choice(guesses) if guesses and (not plain or rng.random() < guess_rate) else rng.choice(plain)
        text = {"ask": f"q{len(state.events)}?", "answer": f"a{len(state.events)}"}.get(state.phase, "")
        submit_action(state, r.pid, action, text=text)
    return state
