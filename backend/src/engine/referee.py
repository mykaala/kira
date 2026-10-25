"""Legal moves and validation. The referee never trusts a model's action."""

from .config import ModeConfig
from .models import GameState


def legal_actions(mode: ModeConfig, state: GameState, pid: str) -> list[str]:
    return mode.legal_actions(state, state.player(pid))


def validate(mode: ModeConfig, state: GameState, pid: str, action: str) -> str | None:
    """None if the action is legal, otherwise an error message an agent can retry with."""
    legal = legal_actions(mode, state, pid)
    if not legal:
        return f"you have no action in the {state.phase} phase"
    if action not in legal:
        return f"'{action}' is not legal; choose one of: {', '.join(legal)}"
    return None
