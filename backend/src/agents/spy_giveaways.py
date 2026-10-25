"""The giveaway-word check: does a civilian's question or answer contain a word that strongly signals the true
place or its cluster? Word lists come from spy_giveaways.json (generated once offline, then reviewed). Matching
is whole-word, case-insensitive, with simple stems (plural, -ed, -ing, -er)."""

import json
import re
from functools import lru_cache
from pathlib import Path

from engine.modes.spy_location import CLUSTER_OF

PATH = Path(__file__).with_name("spy_giveaways.json")
SUFFIX = r"(?:s|es|'s|’s|ed|d|ing|er|ers)?"


def _pattern(word: str) -> str:
    parts = [re.escape(p) for p in word.split()]
    last = parts[-1]
    # skate -> skating, skater: an -e word may drop its e before a suffix
    stem = f"(?:{last}|{last[:-1]}(?=ing|er|ed))" if last.endswith("e") and len(last) > 3 else last
    return r"\b" + r"[\s-]+".join([*parts[:-1], stem]) + SUFFIX + r"\b"


@lru_cache
def _lists() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    data = json.loads(PATH.read_text())
    return data["places"], data["clusters"]


@lru_cache
def _matchers(location: str) -> list[tuple[str, re.Pattern]]:
    places, clusters = _lists()
    words = sorted({*places[location], *clusters[CLUSTER_OF[location]]}, key=len, reverse=True)
    return [(w, re.compile(_pattern(w), re.I)) for w in words]


def giveaway(text: str, location: str) -> str | None:
    """The first giveaway word for this location (or its cluster) that the text uses, or None."""
    return next((w for w, rx in _matchers(location) if rx.search(text)), None)
