"""Cheap checks before a message is posted."""

import re

from .personas import NICKNAMES

MAX_WORDS = 25
BREAKS_CHARACTER = re.compile(
    r"\b(as an ai|an ai (language )?model|language model|i am an ai|i'm an ai|chatgpt|openai)\b", re.I
)


def _is_yelling(word: str) -> bool:
    letters = [c for c in word if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters)


def texting_style(text: str) -> str:
    """Group-chat style whatever the model wrote: lowercase except ALL-CAPS yelling,
    no em dashes or semicolons, no full stop at the end."""
    text = re.sub(r"\s*[—–]\s*", ", ", text).replace(";", ",")
    text = " ".join(w if _is_yelling(w) else w.lower() for w in text.split())
    if text.endswith(".") and not text.endswith(".."):
        text = text[:-1]
    return text


# Distinctive stock words the whole table leaned on in self-play. Each is allowed a few uses per game
# across all players (the cap is in settings); once spent, prompts ban it.
CAPPED_PHRASES = {
    "convenient": r"\bconvenient(?:ly)?\b",
    "staged": r"\bstag(?:ed|ing|e)\b",
    "pile-on": r"\bpil(?:e|ing)[- ]?on\b|\bdog[- ]?pil(?:e|ed|ing)\b",
    "leap": r"\bleap(?:s|ing|ed|t)?\b",
    "proves nothing": r"\bprov(?:es|ed|ing) nothing\b",
    "lazy": r"\blazy\b",
    "reeks": r"\breek(?:s|ing|ed)?\b",
    "too neat": r"\btoo neat\b",
    "tidy": r"\btid(?:y|ier|iest)\b",
}
_CAPPED_RX = {k: re.compile(v, re.I) for k, v in CAPPED_PHRASES.items()}


def capped_uses(text: str) -> list[str]:
    """Each capped phrase this message uses, once per use."""
    return [k for k, rx in _CAPPED_RX.items() for _ in rx.finditer(text)]


def used_up_retry(words: list[str]) -> str:
    return f"you used a used-up word ({', '.join(words)}). Say it another way, in your own voice."


MIN_SHORT_NAME = 3  # "marg" for Marguerite, "tob" for Tobiah


def _forms(name: str) -> list[str]:
    """The name, its short forms (prefixes of 3+ letters) and its nicknames, longest first."""
    forms = [name[:k] for k in range(len(name), MIN_SHORT_NAME - 1, -1)] + NICKNAMES.get(name, [])
    return sorted(set(forms), key=len, reverse=True)


def name_pattern(name: str) -> str:
    """A player's name, a short form of it or a nickname, as a whole word."""
    return r"\b(?:" + "|".join(re.escape(f) for f in _forms(name)) + r")\b"


def _name_alts(name: str) -> str:
    """The name or its short forms, for use inside a larger pattern (no word boundaries)."""
    return "(?:" + "|".join(re.escape(f) for f in _forms(name)) + ")"


def _is_short_for(word: str, name: str) -> bool:
    return word.lower() in {f.lower() for f in _forms(name)}


def names(text: str, name: str) -> bool:
    """The message mentions this player by name or a short form of it."""
    return bool(re.search(name_pattern(name), text, re.I))


def check_say(text: str) -> tuple[str, str | None]:
    """The cleaned message, and an error if it must be retried."""
    text = " ".join(text.split())
    if not text:
        return text, "`say` was empty; write a message"
    if BREAKS_CHARACTER.search(text):
        return text, "you broke character; you are a person at a game night, not an AI"
    words = texting_style(text).split(" ")
    return " ".join(words[:MAX_WORDS]).rstrip(",:"), None


# --- reference check: don't attribute statements to people who never made them -----------

REFERENCE_RETRY = "You referred to a statement that was not made. " "Rewrite using only what is in the transcript."

ROLE_WORDS = {
    "detective": r"detective|cop|det",
    "doctor": r"doctor|doc|medic",
    "bodyguard": r"bodyguard|guard",
    "villager": r"villager|vanilla|plain town",
}
_ROLE = "|".join(f"(?P<{role}>{words})" for role, words in ROLE_WORDS.items())
_STATEMENT = (
    r"(?:claims?|statements?|story|accusations?|defen[cs]e|points?|arguments?|theory|words|comments?"
    r"|reads?|excuse|logic)"
)
_VERB = (
    r"(?:said|says|claimed|claims|claiming|stated|admitted|told|mentioned|insisted|insists|argued|accused"
    r"|suggested|swore|swears|announced|revealed|called|calls)"
)
_ROLE_VERB = (
    r"(?:(?:is\s+|was\s+)?(?:claimed|claims|claiming)|said|says|swore|swears|insisted|insists|admitted"
    r"|told\s+(?:us|me|everyone)|outed\s+(?:himself|herself|themselves|themself)\s+as)"
)
_ARTICLE = (
    r"(?:(?:to\s+be|shes|hes|theyre|(?:that\s+)?(?:they|she|he)\s*(?:'re|’re|'s|’s|\s+(?:is|are|was|were)))\s+)?"
    r"(?:the\s+|a\s+|real\s+)*"
)
_ADDRESS = re.compile(r"^\s*(?:\w+\s+){0,2}?(\w+)\s*,")  # "toby, ..." or "nah toby, ..."
# "Dara claimed detective", "Dara's doctor claim", "Dara said she's the detective"
_ROLE_BY_NAME = [
    rf"\b{{n}}\s+(?:already\s+|just\s+|literally\s+|now\s+)?{_ROLE_VERB}\s+{_ARTICLE}(?:{_ROLE})\b",
    rf"\b{{n}}(?:'s|’s)\s+(?:{_ROLE})\s+claim\b",
]
_ROLE_BY_YOU = [
    rf"\byou\s+(?:already\s+|just\s+)?(?:claimed|said\s+you\s*(?:'re|’re|\s+are|\s+were))\s+"
    rf"(?:to\s+be\s+)?(?:the\s+|a\s+|real\s+)*(?:{_ROLE})\b",
    rf"\byour\s+(?:{_ROLE})\s+claim\b",
]
_SELF_CLAIM = [
    rf"\b(?:i['’]?m|i\s+am|i\s+was|as\s+the|i['’]?m\s+claiming|claiming)\s+"
    rf"(?:the\s+|a\s+|real\s+|actually\s+|just\s+|plain[- ]?)*(?:{_ROLE})\b",
    rf"\b(?:{_ROLE})\s+here\b",
]
_SELF_CHECK = re.compile(r"\bi\s+(?:checked|investigated|cleared)\b|\bmy\s+(?:check|investigation|result)\b", re.I)


def _first(patterns: list[str], text: str) -> re.Match | None:
    return next((m for p in patterns if (m := re.search(p, text, re.I))), None)


_SAID_BY_NAME = (
    rf"\b{{n}}(?:'s|’s)\s+(?:\w+\s+)?{_STATEMENT}\b|\b{{n}}\s+(?:\w+\s+)?{_VERB}\b"
    rf"|\baccording\s+to\s+{{n}}\b|\bas\s+{{n}}\s+(?:put|said)\s+it\b"
    rf"|\b{{n}}(?:'s|’s)\s+(?:\w+\s+){{{{0,3}}}}thing\b"
)
_SAID_BY_YOU = re.compile(rf"\b(?:you\s+(?:just\s+|already\s+)?{_VERB}|your\s+(?:\w+\s+)?{_STATEMENT})\b", re.I)


def roles_claimed(messages: list[str]) -> set[str]:
    """Roles a player has claimed in their own words ("im the detective", "doctor here")."""
    out = set()
    for m in messages:
        for p in _SELF_CLAIM:
            for hit in re.finditer(p, m, re.I):
                out |= _roles_in(hit)
        if _SELF_CHECK.search(m):  # reporting a result is a detective claim
            out.add("detective")
    return out


def _roles_in(match: re.Match) -> set[str]:
    return {role for role, v in match.groupdict().items() if v}


def flag_reason(flagged: list[tuple[str, str]]) -> str:
    return "; ".join(why for _, why in flagged)


def unsupported_references(
    text: str, speaker: str, said: dict[str, list[str]], claimed: dict[str, set[str]]
) -> list[tuple[str, str]]:
    """(name, reason) for each statement this message attributes to a player who never made it,
    judged against the whole game: `said` is every message each player has posted, `claimed` the
    roles each has claimed (the claims log plus their own words). Only two things are checked,
    cheaply: quoting someone who has never spoken, and saying someone claimed a role they never
    claimed."""
    flagged: list[tuple[str, str]] = []
    names = [n for n in said if n != speaker]
    lead = _ADDRESS.match(text)
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        start = _ADDRESS.match(sentence) or lead
        addressee = next((n for n in names if start and _is_short_for(start[1], n)), None)
        for name in names:
            if name in {f for f, _ in flagged}:
                continue
            n = _name_alts(name)
            by_you = name == addressee
            role_hit = _first([p.format(n=n) for p in _ROLE_BY_NAME], sentence) or (
                by_you and _first(_ROLE_BY_YOU, sentence)
            )
            if role_hit:
                missing = _roles_in(role_hit) - claimed.get(name, set()) - roles_claimed(said.get(name, []))
                if missing:
                    flagged.append((name, f"says {name} claimed {'/'.join(sorted(missing))}, but they never did"))
                continue
            quoted = re.search(_SAID_BY_NAME.format(n=n), sentence, re.I) or (by_you and _SAID_BY_YOU.search(sentence))
            if quoted and not said.get(name):
                flagged.append((name, f"quotes {name}, who hasn't said anything this game"))
    return flagged
