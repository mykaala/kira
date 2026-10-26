"""Free-text location guesses: nobody sees the location list, so the spy names a place in its own words and the
server decides whether it is the secret location: fixed rules first (exact name, alias, name plus modifiers, a
typo, another place's name, part of the name), then a cheap judge call for whatever is left, remembered across
runs. Every decision records the rule that made it, for audit."""

import asyncio
import json
import re
import time
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from engine.modes.spy_location import LOCATION_NAMES
from server.settings import BACKEND, Settings

from .costlog import CostLog, cost_usd
from .llm import LLM, Usage
from .schemas import _strict

MAX_WORDS = 6
ARTICLES = {"a", "an", "the"}
# words a guess may add to the true name and still match ("a public swimming pool")
MODIFIERS = {
    "a",
    "an",
    "the",
    "public",
    "indoor",
    "outdoor",
    "local",
    "small",
    "big",
    "large",
    "city",
    "busy",
    "crowded",
    "old",
    "new",
}
ALIASES_PATH = Path(__file__).with_name("spy_guess_aliases.json")
MEMO_PATH = BACKEND / "runs" / "spy_guess_memo.json"  # judge verdicts, kept across runs

JUDGE_SYSTEM = """You decide whether a guess names a secret place in a party game.
Rule: the guess matches only if it is the same place or a clear synonym for it. A broader category (for example
"somewhere with water" for a swimming pool), a different place (even a similar one), several options, or a hedged
answer ("maybe a gym") is NOT a match. Judge the words of the guess only.
Answer with JSON only: {"reason": a few words, "match": true or false}."""


def guess_schema() -> dict:
    """The spy's free-text guess: one specific place, or null (null keeps playing; illegal at the last chance)."""
    return _strict("guess", {"guess": {"anyOf": [{"type": "string"}, {"type": "null"}]}})


def judge_schema() -> dict:
    return _strict("guess_judge", {"reason": {"type": "string"}, "match": {"type": "boolean"}})


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and word[-3] in "sxz":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def normalize(text: str) -> str:
    """Lowercase, no punctuation or articles, simple plural stems: "The Dentist's Office!" -> "dentist office"."""
    text = re.sub(r"['’]", "", text.lower())
    words = re.findall(r"[a-z0-9]+", text)
    return " ".join(_stem(w) for w in words if w not in ARTICLES)


def guess_error(guess: str | None, allow_null: bool) -> str | None:
    """Why this guess isn't one specific place, or None."""
    if guess is None or not guess.strip():
        return None if allow_null else "name one place; null is not allowed now"
    g = guess.strip()
    if len(g.split()) > MAX_WORDS:
        return f"name the place in at most {MAX_WORDS} words"
    if "," in g or "/" in g or ";" in g or re.search(r"\b(or|and/or|either)\b", g, re.I):
        return "name one single place, not several options"
    return None


class GuessDecision(BaseModel):
    guess: str
    normalized: str
    truth: str
    match: bool
    rule: str  # exact | alias | modifier | typo | other_place | partial | judge | judge_memo | judge_failed
    reason: str


def _edit1(a: str, b: str) -> bool:
    """Edit distance at most 1."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def is_subphrase(small: str, big: str) -> bool:
    """`small` is a whole-word run inside `big`, and shorter than it ("airport" in "airport lounge")."""
    s, b = small.split(), big.split()
    return 0 < len(s) < len(b) and any(b[i : i + len(s)] == s for i in range(len(b) - len(s) + 1))


def _with_modifiers(guess: str, form: str) -> bool:
    """The guess is the form plus only words from the fixed modifier list ("public swimming pool")."""
    g, f = guess.split(), form.split()
    for i in range(len(g) - len(f) + 1):
        if g[i : i + len(f)] == f and all(w in MODIFIERS for w in g[:i] + g[i + len(f) :]):
            return len(g) > len(f)
    return False


def _typo(guess: str, form: str) -> bool:
    """Same words, except words of 6+ letters may be one edit apart ("planetarum")."""
    g, f = guess.split(), form.split()
    return (
        len(g) == len(f)
        and g != f
        and all(x == y or (len(x) >= 6 and len(y) >= 6 and _edit1(x, y)) for x, y in zip(g, f))
    )


@lru_cache
def guess_aliases() -> dict[str, list[str]]:
    """Other names per place for matching guesses (generated offline, reviewed): spy_guess_aliases.json."""
    return json.loads(ALIASES_PATH.read_text())["aliases"] if ALIASES_PATH.exists() else {}


def place_forms(place: str) -> tuple[str, set[str]]:
    """(the normalized name, its normalized aliases)."""
    return normalize(place), {normalize(a) for a in guess_aliases().get(place, [])}


def deterministic(guess: str, truth: str) -> tuple[bool, str] | None:
    """(match, rule) from the fixed rules, in order, or None if they leave it to the judge."""
    n = normalize(guess)
    name, aliases = place_forms(truth)
    forms_ = {name, *aliases}
    if n == name:
        return True, "exact"
    if n in aliases:
        return True, "alias"
    if any(_with_modifiers(n, f) for f in forms_):
        return True, "modifier"
    if any(_typo(n, f) for f in forms_):
        return True, "typo"
    if any(n in {o_name, *o_aliases} for o in LOCATION_NAMES if o != truth for o_name, o_aliases in [place_forms(o)]):
        return False, "other_place"
    if any(is_subphrase(n, f) for f in forms_):
        return False, "partial"
    return None


def which_place(guess: str) -> str | None:
    """The pool place a guess names outright (its name or an alias), if any: for where wrong guesses land."""
    n = normalize(guess)
    return next((p for p in LOCATION_NAMES if n in {place_forms(p)[0], *place_forms(p)[1]}), None)


class GuessMatcher:
    """Decides guesses; judge verdicts are kept in a memo file across runs, keyed by (normalized guess, place)."""

    def __init__(self, llm: LLM, settings: Settings, log: CostLog, memo_path: Path = MEMO_PATH):
        self.llm, self.settings, self.log, self.memo_path = llm, settings, log, memo_path
        self.memo: dict[str, dict] = json.loads(memo_path.read_text()) if memo_path.exists() else {}

    def _save(self) -> None:
        self.memo_path.parent.mkdir(parents=True, exist_ok=True)
        self.memo_path.write_text(json.dumps(self.memo, indent=1, sort_keys=True) + "\n")

    async def decide(self, *, game_id: str, guess: str, truth: str) -> GuessDecision:
        n = normalize(guess)
        base = {"guess": guess, "normalized": n, "truth": truth}
        if hit := deterministic(guess, truth):
            return GuessDecision(**base, match=hit[0], rule=hit[1], reason="fixed rule")
        key = f"{n}|{truth}"
        if key in self.memo:
            m = self.memo[key]
            return GuessDecision(**base, match=m["match"], rule="judge_memo", reason=m["reason"])
        verdict = await self._judge(game_id, guess, truth)
        if verdict is None:  # never memoized: a later run asks again
            return GuessDecision(**base, match=False, rule="judge_failed", reason="judge failed twice")
        self.memo[key] = {"match": verdict[0], "reason": verdict[1], "model": self.settings.model_for("guess_judge")}
        self._save()
        return GuessDecision(**base, match=verdict[0], rule="judge", reason=verdict[1])

    async def _judge(self, game_id: str, guess: str, truth: str) -> tuple[bool, str] | None:
        s = self.settings
        model = s.model_for("guess_judge")
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"Secret place: {truth}\nGuess: {guess}"},
        ]
        for attempt in range(2):
            usage, raw, start, error, out = Usage(), "", time.perf_counter(), None, None
            try:
                async with asyncio.timeout(s.call_timeout_s):
                    async for chunk in self.llm.stream(
                        model=model,
                        messages=messages,
                        schema=judge_schema(),
                        max_tokens=s.max_output_tokens_guess,
                        reasoning_effort=s.effort_for("guess_judge"),
                        usage=usage,
                    ):
                        raw += chunk
                obj = json.loads(raw)
                out = (bool(obj["match"]), str(obj["reason"])[:200])
            except Exception as e:  # noqa: BLE001 - retried, then the guess counts as no match (flagged)
                error = f"{type(e).__name__}: {e}"
            self.log.call(
                game_id=game_id,
                player="guess_judge",
                call_type="guess_judge",
                model=model,
                attempt=attempt,
                input_tokens=usage.input_tokens,
                cached_tokens=usage.cached_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                cost_usd=cost_usd(s.prices, model, usage.input_tokens, usage.cached_tokens, usage.output_tokens),
                latency_ms=(time.perf_counter() - start) * 1000,
                valid=int(out is not None),
                error=error,
                prompt=json.dumps(messages),
                response=raw,
            )
            if out:
                return out
        return None
