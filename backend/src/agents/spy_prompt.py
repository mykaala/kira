"""Prompt builder for the hidden-location game, in the same three parts as Mafia's so caching applies:
1. a shared block (rules, both role guides, how to ask, answer, vote and name the location, texting
   style, every answer format) that is byte-identical for every agent, role and call type;
2. the persona (Mafia's persona block, unchanged);
3. the dynamic part: the table, your secret role (the location only if you are a civilian), the
   questions so far, your plan for this turn, and the task."""

import json
from functools import lru_cache

from engine.modes.spy_location import GUESS, LOCATION_NAMES, RULES
from engine.views import PlayerView

from . import checks
from .personas import Persona

ROLE_GUIDES = """ROLE GUIDES (you will be told which one is yours)
- CIVILIAN. You know the location. Find the spy: the one whose questions and answers don't quite fit the place,
  who stays oddly general, or who copies other people's details. Prove you belong without handing the spy the
  location: every detail you give, the spy hears too. Never say the location's name, a word that is basically its
  name, or a detail so specific it gives the place away.
- SPY. You don't know the location; everyone else does. Never say or hint that you are the spy, and never ask what
  the location is. Listen to every question and answer: each one rules places in or out. Answer like someone who
  belongs, in a way that fits the likeliest locations at once. Ask questions that sound natural but make people
  reveal more. When you're told you may name the location, do it only if the clues point clearly at one place."""

PLAY = """HOW TO ASK
- Ask the player you picked one short question, the kind someone who was really there could answer easily.
- Good questions are about the place, not the person: what you'd hear, wear, carry, smell, pay for, who works
  there, what time people show up, what goes wrong there, how long you stay.
- Never ask a question that is already in the record, or the same question in other words. Find a new angle.
- Pick your target with a reason: someone whose last answer felt off, someone who hasn't been tested much, or
  someone you want to clear. You can't ask the player who just asked you, unless nobody else is left.
- Don't ask yes-or-no questions that give the place away, and don't name any location in a question.

HOW TO ANSWER
- Answer the question you were asked, in a few words, the way a person at the place would.
- Be specific enough that other civilians know you belong, but not so specific that the spy can name the place.
  A good answer fits the real location and a few others. A useless answer fits all twenty.
- Never repeat someone else's answer or detail. Never name a location.

HOW TO VOTE
- Vote for the player you think is the spy: whose questions or answers fit the location worst, who stayed vaguest,
  who echoed others, or who asked things a civilian would already know. You can't vote for yourself or abstain.
- Think for yourself; don't just vote with whoever seems to be the favourite.
- If you are the spy, vote for a civilian, ideally one whose answers already looked shaky.

NAMING THE LOCATION (the spy only)
- On a turn where you may name it, compare every answer so far with each location on the list. If one place fits
  clearly better than the rest, name it. If two or more still fit, return null and keep asking; a wrong name loses
  the game at once.
- If the vote catches you, you get one last chance: name your single best guess. Any answer beats none.

STAYING IN CHARACTER
- You are a person at a game night, never an AI or assistant. No lists, no stage directions, no quoting the rules.
- Only refer to things that are in the record. Don't claim someone said something they didn't."""

TEXTING = """HOW YOU TEXT
- This is a group chat on phones. Text like a real person: lowercase, light punctuation, fragments are fine.
- Short. A question is under 15 words. An answer is usually under 10 words. Never a paragraph.
- Slang when it fits you: lol, ngl, idk, tbh, fr, nah, wait, ok so.
- Sound like yourself: your voice card says how you talk. Don't borrow other players' words.
- No polite filler, no summing up, no em dashes, no semicolons, no quotation marks around words.
- The vibe (don't copy these): ok but what do u usually wear there / lol depends who's paying / mostly the smell ngl
  / nah u wait in line forever / bo what's the first thing u do when u get there"""

FORMATS = """YOUR ANSWER (JSON only, nothing else)
- Ask turn: {"target": the player's name, "question": your question}.
- Answer turn: {"text": your answer}.
- Vote: {"target": the player's name}. Nothing else: nothing you write is shown.
- Naming the location: {"location": one location from the list, exactly as written, or null to keep playing}."""


@lru_cache
def shared_block() -> str:
    """Identical for every agent, role and call type of this mode, so it is cached across the table."""
    return "\n\n".join([f"GAME RULES\n{RULES}", ROLE_GUIDES, PLAY, TEXTING, FORMATS])


def known_location(view: PlayerView) -> str | None:
    """The location, if this view may know it (civilians only: it arrives on their channel)."""
    e = next((e for e in view.events if e.kind == "location"), None)
    return e.text.removeprefix("The location is: ").removesuffix(".") if e else None


def role_card(view: PlayerView) -> str:
    loc = known_location(view)
    if view.role == "spy":
        return "YOUR SECRET ROLE: SPY. You don't know the location. Work it out, and don't get caught."
    return f"YOUR SECRET ROLE: CIVILIAN. THE LOCATION: {loc}. Never say it."


def _record(view: PlayerView) -> list[str]:
    names = {p.id: p.name for p in view.players}
    lines = []
    for e in view.events:
        if e.kind == "ask":
            lines.append(f"{names[e.actor]} asks {names[e.target]}: {e.text}")
        elif e.kind == "answer":
            lines.append(f"{names[e.actor]}: {e.text}")
        elif e.kind in ("first", "info", "vote", "accused"):
            lines.append(f"[game] {e.text}")
    return lines


PLANS = {
    ("civilian", "ask", "probe"): "Ask something a real visitor could answer at once but the spy would have to fake. "
    "Aim it at someone you aren't sure about.",
    ("civilian", "ask", "vague"): "Ask something broad and safe, so the spy learns nothing from your question; "
    "judge the answer.",
    ("civilian", "answer", "probe"): "Answer with one detail that fits the location, so the civilians know you're "
    "one of them, but not enough for the spy to name the place.",
    ("civilian", "answer", "vague"): "Keep it vague: true at the location, but true at plenty of others too.",
    ("spy", "ask", "blend"): "Ask something natural that would make sense at many places, and pick someone whose "
    "answer will narrow it down.",
    ("spy", "answer", "blend"): "Answer so it fits the likeliest locations from what you've heard so far, and "
    "sounds sure of itself.",
}

TASKS = {
    "ask": "Your turn to ask. Pick a `target` and write a `question`.",
    "answer": "{asker} asked you: {question}\nYour turn to answer. Write `text`.",
    "vote": "Time to vote. Choose who you think is the spy in `target`.",
    "spy_guess": "Your turn to ask, and you may name the location instead. If the clues point clearly at one "
    "place, set `location` to it. Otherwise set `location` to null; you'll ask a question next.",
    "last_chance": "The vote caught you. Name the location now: set `location` to your single best guess.",
}


def choices(view: PlayerView, call_type: str) -> list[str]:
    """What is legal right now, as the model sees it: player names, or locations."""
    names = {p.id: p.name for p in view.players}
    if call_type in ("spy_guess", "last_chance"):
        return [a.removeprefix(GUESS) for a in view.legal_actions if a.startswith(GUESS)]
    return [names[a] for a in view.legal_actions if a in names]


def observation(view: PlayerView, persona: Persona, call_type: str, error: str | None = None) -> str:
    names = {p.id: p.name for p in view.players}
    record = _record(view)
    asked = sum(e.kind == "ask" for e in view.events)
    my_last = next((e.text for e in reversed(view.events) if e.kind in ("ask", "answer") and e.actor == view.you), None)
    parts = [
        f"PLAYERS AT THE TABLE: {', '.join(p.name for p in view.players)}",
        f"You are {names[view.you]}.",
        role_card(view),
        f"QUESTIONS SO FAR: {asked} of about {2 * len(view.players)}.",
        "THE RECORD:\n" + ("\n".join(record) or "nothing yet"),
    ]
    if my_last:
        parts.append(f"Your last line (don't repeat it): {my_last}")
    plan = (view.intent or {}).get("plan")
    if text := PLANS.get((view.role, call_type, plan)):
        parts.append(f"YOUR PLAN FOR THIS TURN (secret): {text}")
    task = TASKS[call_type]
    if call_type == "answer":
        last = next(e for e in reversed(view.events) if e.kind == "ask")
        task = task.format(asker=names[last.actor], question=last.text)
    if call_type in ("ask", "answer"):
        task += f" Keep it short: at most {checks.MAX_WORDS} words."
    legal = choices(view, call_type)
    if call_type in ("ask", "vote"):
        task += f"\nLegal `target` values: {json.dumps(legal)}"
    elif call_type == "last_chance" and len(legal) < len(LOCATION_NAMES):
        task += f"\nLegal `location` values: {json.dumps(legal)}"
    parts.append(f"YOUR TASK: {task}")
    if error:
        parts.append(f"Your previous answer was rejected: {error}")
    return "\n\n".join(parts)
