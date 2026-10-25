"""Output schemas for the hidden-location game: one fixed schema per call type. Every enum lists the
whole cast or every location, so a schema is the same for every call of its type in a game (and
cached); who or what is actually legal right now is checked in code."""

from engine.modes.spy_location import LOCATION_NAMES

from .schemas import _strict


def ask_schema(names: list[str]) -> dict:
    return _strict("ask", {"target": {"type": "string", "enum": names}, "question": {"type": "string"}})


def answer_schema() -> dict:
    return _strict("answer", {"text": {"type": "string"}})


def vote_schema(names: list[str]) -> dict:
    return _strict("vote", {"target": {"type": "string", "enum": names}})


def spy_guess_schema() -> dict:
    """Name the location, or null to keep playing. The last-chance guess uses it too (null is
    illegal there, which code checks)."""
    location = {"anyOf": [{"type": "string", "enum": LOCATION_NAMES}, {"type": "null"}]}
    return _strict("spy_guess", {"location": location})


def judge_schema() -> dict:
    """Offline harness only: every location an answer would fit."""
    fits = {"type": "array", "items": {"type": "string", "enum": LOCATION_NAMES}}
    return _strict("judge", {"fits": fits})
