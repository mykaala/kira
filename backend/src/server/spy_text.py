"""What a person types, made safe before it enters the game: control characters and markup stripped, length
capped. The AIs only ever see it as quoted, untrusted player speech (agents/spy_prompt.py quotes every
player's lines the same way, so nothing marks which seat is the human)."""

import html
import re
import unicodedata

from agents.spy_guess import guess_aliases
from engine.modes.spy_location import names_location

MAX_WORDS = 25
MAX_CHARS = 200

_TAG = re.compile(r"<[^>]{0,200}>")  # html/xml-ish tags
_MARKUP = re.compile(r"[`*_~#>|\\\[\]{}]")  # markdown and template punctuation
_LINK = re.compile(r"\]\([^)]*\)|https?://\S+", re.I)


def clean(text: str) -> str:
    """One line of plain words: no control or format characters, no tags, links or markup, single spaces."""
    text = html.unescape(text or "")
    text = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in text)
    text = _LINK.sub(" ", text)
    text = _TAG.sub(" ", text)
    text = _MARKUP.sub(" ", text)
    return " ".join(text.split())


def human_text(text: str) -> str:
    """The cleaned text, or ValueError with a reason the player can act on."""
    out = clean(text)
    if not out:
        raise ValueError("write something first")
    if len(out.split()) > MAX_WORDS:
        raise ValueError(f"keep it to {MAX_WORDS} words")
    if len(out) > MAX_CHARS:
        raise ValueError(f"keep it to {MAX_CHARS} characters")
    return out


def names_place(text: str, place: str) -> str | None:
    """The name or alias of `place` the text uses, if any (for the soft warning to a civilian)."""
    if names_location(text, place):
        return place
    return next(
        (a for a in guess_aliases().get(place, []) if re.search(r"\b" + re.escape(a) + r"\b", text, re.I)), None
    )
