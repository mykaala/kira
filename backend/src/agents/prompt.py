"""Prompt builder, in three parts so prompt caching applies:
1. a shared block (rules, every role guide, how to play, voice guidance, the answer formats) that is
   byte-identical for every agent, role and game of a mode, and long enough (over 1,024 tokens) to cache;
2. the persona, identical for that character all game;
3. the dynamic part: who is at the table, your secret role, the record, and the task."""

import json
from functools import lru_cache

from engine.models import ABSTAIN, PUBLIC
from engine.views import PlayerView

from . import checks
from .personas import Persona
from .schemas import BeliefState

NO_ACTION = "none"
TRANSCRIPT_LINES = 120

ROLE_GUIDE = {
    "mafia": (
        "MAFIA. Your team wins by surviving until you equal the others. Never reveal or hint that you are "
        "mafia. Keep a consistent cover story (usually: plain villager); before you speak, check `my_claims` in "
        "your notes and never contradict it. Steer suspicion toward villagers, but don't pile onto the same "
        "person as your partner. Never defend a partner so hard it links you. Don't vote the same target as "
        "your partner unless the town is already on that player, and don't openly agree with your partner or "
        "back up their points. Follow your secret plan for today when you are given one."
    ),
    "detective": (
        "DETECTIVE. Each night you learn whether one player is mafia. Your results are real; use them. "
        "Revealing yourself makes you a night target, so choose the moment carefully, and follow your "
        "secret plan for today when you are given one. Any result you claim must be one you actually got."
    ),
    "doctor": (
        "DOCTOR. Each night you protect one player (yourself allowed, never the same player two nights "
        "running) from the mafia kill. Revealing yourself makes you a target, so think twice before you do."
    ),
    "villager": (
        "VILLAGER. You have no secret information. Find the mafia from what people say, what they claim, "
        "and how they vote, and push the town toward them."
    ),
    "jester": (
        "JESTER. You win alone, and only, if the town votes you out. Be suspicious enough to draw votes but "
        "never obviously trying to get eliminated; never reveal that you are the jester."
    ),
    "bodyguard": (
        "BODYGUARD. Each night you guard one other player; if the mafia attack them, you die in their "
        "place. Revealing yourself makes you a target."
    ),
}

PLAY = """HOW TO PLAY WELL
- Stay in character at all times. You are a person at a game night, never an AI or assistant.
- Only refer to statements that appear in the record. Never say a player claimed or said something unless it is
  there. If nobody has spoken yet today, there is nothing to react to: open with your own read.
- Only state as fact what is in the public record, or what your role privately told you. You may lie only if it
  serves your team, and must stay consistent with your own past claims.
{deaths}
- Day 1: the mafia can't kill on the first night, so nobody has died yet. Don't talk about a missing kill,
  a "quiet night", a doctor save, or what the mafia did overnight.
- Anyone can claim anything. A lone claim is evidence you can't verify, not proof. If two players claim the
  same role, one of them is lying: weigh who benefits, and check each claim against {follow}.
- A detective claim that names someone as mafia is strongest when it comes early and stays the same. A result
  that changes, or a claim made only once the claimer is under pressure, deserves suspicion.
- Push back on at least one claim or accusation per day. Don't just agree with whoever spoke last.
- `accuses`: the one player your message points at as a suspect, or null if it doesn't point at anyone. It is
  public (the table sees "you -> them") and must match who your text is about.
- `claim`: if your message says you are a role, fill it with that role; for a detective result also the player
  checked and the result. Otherwise null.
- No lists, no stage directions, no quoting the rules.
- Some overused words get banned for the rest of the game once the table has used them up. If you are told a
  word is used up, don't use it or its forms; say what you mean another way."""

TEXTING = """HOW YOU TEXT
- This is a group chat on phones. Text like a real person: lowercase, light punctuation, fragments are fine.
- ALL CAPS only when you're yelling or really heated.
- Short. Usually one line. Most messages are under 10 words. Never a paragraph.
- Slang when it fits you: lol, ngl, idk, tbh, fr, nah, wait, bro, sus, ok so.
- You're competing, not hosting. No polite filler ("fair point", "i hear you", "let's all", "to be clear"),
  no summing up the chat, no asking everyone for their reads.
- Be blunt: accuse, deflect, get defensive, tease, get annoyed. A little rude is fine.
- Plain everyday words, not analyst words (no "concrete", "consistent", "opportunistic", "narrative", "evidence").
- Sound like yourself, not like the table: your voice card says how you talk. Don't borrow other players' words.
- Nobody is "quiet" just because they haven't had their turn yet.
- No em dashes, no semicolons, no quotation marks around words.
- The vibe (don't copy these): wait why are we on juno / nah toby ur reaching / kofi WHAT / ok im voting mei
  sorry / lol no / idk dara feels off ngl"""

FORMATS = """YOUR ANSWER (JSON only, nothing else)
- Discussion turn: {"say": your message, "accuses": a player's name or null, "claim": null or
  {"role": ..., "target": a player's name or null, "result": "mafia" | "not mafia" | null},
  "state": your private notes}. `state` is: a 0-10 suspicion score for every other living player, the few
  claims you heard that matter most (at most 6, a few words each), your own public claims (at most 6), and a
  one-line plan. Only you ever see `state`.
- Vote or night turn: {"action": one of the legal values}. Nothing else: nothing you write is shown."""


DEATHS = {  # the lines that depend on whether roles are revealed on death
    True: (
        "- Votes are public and permanent. Who voted with whom, and who switched late, is real information. So is who\n"
        "  pushed hardest for a player who flipped town.\n"
        "- When someone is eliminated or killed, their role is revealed. Use every flip: whoever pushed a villager out,\n"
        "  or defended someone who flipped mafia, has some explaining to do.",
        "the flips that follow",
    ),
    False: (
        "- Votes are public and permanent. Who voted with whom, and who switched late, is real information.\n"
        "- Roles are NOT revealed when someone is eliminated or killed; nobody learns them until the game ends.\n"
        "  Never say a dead player was or wasn't mafia as if it were known. Who the mafia chose to kill at night,\n"
        "  and who pushed hardest for each player voted out, are your clues instead.",
        "what happens next",
    ),
}


@lru_cache
def shared_block(rules: str, roles_revealed: bool = True) -> str:
    """Identical for every agent of a mode (and setting), so it is cached across the whole table."""
    guides = "\n".join(f"- {text}" for text in ROLE_GUIDE.values())
    return "\n\n".join(
        [
            f"GAME RULES\n{rules}",
            f"ROLE GUIDES (you will be told which one is yours)\n{guides}",
            PLAY.format(deaths=DEATHS[roles_revealed][0], follow=DEATHS[roles_revealed][1]),
            TEXTING,
            FORMATS,
        ]
    )


def persona_block(persona: Persona) -> str:
    """The character, with a voice card of three sample lines. Identical for this character all game."""
    text = (
        f"YOUR CHARACTER\nYou are {persona.name}, {persona.voice.lower()}. Style: {persona.style}. "
        f"Suspicion bias: {persona.suspicion}. When holding a secret: {persona.lying}. "
        f"Stubbornness: {persona.stubbornness}.\n"
        f"Voice card (how you sound; don't reuse these lines): "
        f"{' / '.join(line.lower() for line in persona.sample_lines)}"
    )
    if traits := persona.trait_text():
        text += f"\nTemperament: {traits}."
    if persona.strategy:
        text += f"\n{persona.strategy}"
    return text


def role_card(view: PlayerView) -> str:
    names = {p.id: p.name for p in view.players}
    card = f"YOUR SECRET ROLE: {view.role.upper()} (see its role guide). Your team: {view.team}."
    if view.teammates:
        card += f" Your fellow mafia: {', '.join(names[t] for t in view.teammates)}."
    return card


TASKS = {
    "discussion": (
        "Your turn in the group chat. Write `say`: one short text, about {target} words or fewer, "
        "never more than {words}. React to what was just said, use names. Don't repeat your last "
        "message. Set `accuses` and `claim` (usually null), and update `state`."
    ),
    "vote": (
        "Voting time. Choose who to eliminate (or abstain) in `action`, based on the discussion and your own "
        "suspicions, not on what everyone else seems to think."
    ),
    "night": "It is night. Choose your night target in `action`.",
}


def _format_events(view: PlayerView) -> list[str]:
    names = {p.id: p.name for p in view.players}
    lines = []
    for e in view.events:
        if e.kind == "phase":
            if e.phase == "morning":
                lines.append(f"=== Day {e.day} ===")
            elif e.phase == "night":
                lines.append(f"--- Night {e.day} ---")
            else:
                lines.append(f"--- {e.phase.title()} ---")
        elif e.kind == "morning":
            lines.append(f"[morning] {e.text}")
        elif e.kind == "say":
            lines.append(f"{names[e.actor]}: {e.text}")
        elif e.vis == PUBLIC:
            lines.append(f"[game] {e.text}")
        elif e.vis.startswith("channel:"):
            lines.append(f"[mafia only] {e.text}")
        else:
            lines.append(f"[private to you] {e.text}")
    return lines[-TRANSCRIPT_LINES:]


def _format_claims(view: PlayerView) -> str:
    names = {p.id: p.name for p in view.players}
    lines = []
    for c in view.claims:
        what = (
            f"{c.role}" + (f", checked {names[c.target]}" if c.target else "") + (f": {c.result}" if c.result else "")
        )
        lines.append(f"- {names[c.actor]} (day {c.day}): claims {what}")
    return "\n".join(lines)


def _plan_text(view: PlayerView, call_type: str) -> str | None:
    """A secret plan for today (the mafia's team plan, the detective's timing), as a concrete instruction."""
    plan = view.intent
    if not plan:
        return None
    names = {p.id: p.name for p in view.players}
    if plan["talk"] == "reveal":
        if call_type != "discussion":
            return None
        t = names[plan["claim"]["target"]]
        return (
            f"Reveal now: say you are the detective and that {t} is mafia. Set `claim` to role detective, "
            f"target {t}, result mafia."
        )
    if plan["talk"] == "hold":
        return (
            (
                "Keep your role and results secret today unless someone names or accuses you. Steer suspicion "
                "with ordinary reads instead."
            )
            if call_type == "discussion"
            else None
        )
    partners = ", ".join(names[t] for t in plan["partners"]) or "nobody"
    if plan["talk"] == "night":
        target, why = plan["kill"]
        return (
            f"Tonight's kill: {names[target]}, who {why}. Choose {names[target]} in `action`."
            if call_type == "night"
            else None
        )
    if call_type == "vote":
        return {
            "follow": f"Vote for the town's main suspect, unless that is {partners}. Your partner will vote elsewhere.",
            "own": "Vote for a villager you have pushed on yourself, NOT the town's main suspect and not where "
            "your partner is likely to vote, unless the town is already on them.",
        }.get(plan.get("vote", ""))
    if call_type != "discussion":
        return None
    claim = plan.get("claim")
    if plan["talk"] == "fake_claim":
        return (
            f"Fake-claim DETECTIVE in this message: say you are the detective and checked {names[claim['target']]} "
            f"last night: {claim['result']}. Set `claim` to role detective, target {names[claim['target']]}, result "
            f"{claim['result']}. Afterwards defend it and never contradict it."
        )
    if plan["talk"] == "counterclaim":
        return (
            f"{names[claim['target']]} claimed detective. Counterclaim now: say YOU are the real detective and you "
            f"checked {names[claim['target']]}: mafia. Set `claim` to role detective, target "
            f"{names[claim['target']]}, result mafia. Call their claim a lie."
        )
    if plan["talk"] == "keep_claim":
        return "You publicly claimed detective. Keep that story and defend it; never contradict your claim."
    return "Blend in as a plain villager. Don't claim a role."


def observation(
    view: PlayerView,
    persona: Persona,
    beliefs: BeliefState,
    call_type: str,
    choices: list[str],
    error: str | None = None,
    used_up: list[str] | None = None,
) -> str:
    alive = [p for p in view.players if p.alive and p.id != view.you]
    dead = [f"{p.name} ({p.role})" if p.role else f"{p.name} (role unknown)" for p in view.players if not p.alive]
    my_votes = [e.text for e in view.events if e.kind == "vote" and e.actor == view.you]
    my_last = next((e.text for e in reversed(view.events) if e.kind == "say" and e.actor == view.you), None)
    today = sum(e.kind == "say" and e.day == view.day for e in view.events)
    names = {p.id: p.name for p in view.players}

    parts = [
        f"PLAYERS AT THE TABLE: {', '.join(p.name for p in view.players)}",
        role_card(view),
        f"NOW: Day {view.day}, {view.phase}.",
        f"Alive (besides you): {', '.join(p.name for p in alive)}.",
        f"Dead: {', '.join(dead) or 'nobody yet'}.",
        "PUBLIC RECORD AND WHAT YOU HAVE SEEN:\n" + "\n".join(_format_events(view)),
        f"Messages so far today: {today}." + (" No one has spoken yet today." if today == 0 else ""),
        "ROLE CLAIMS SO FAR (unverified):\n" + (_format_claims(view) or "none"),
        "WHO IS ACCUSING WHOM RIGHT NOW: "
        + (", ".join(f"{names[a]} -> {names[t]}" for a, t in view.accusations.items()) or "nobody yet"),
        f"Your own past votes: {'; '.join(my_votes) or 'none yet'}.",
        f"Your private notes from last turn: {beliefs.model_dump_json()}",
    ]
    if my_last:
        parts.append(f"Your last message (don't repeat it): {my_last}")
    if plan := _plan_text(view, call_type):
        parts.append(f"YOUR PLAN FOR TODAY (secret): {plan}")
    if used_up and call_type == "discussion":
        parts.append(f"USED UP, don't use these words: {', '.join(used_up)}")
    task = TASKS[call_type].format(words=checks.MAX_WORDS, target=min(12, max(4, persona.talk_words // 3)))
    if call_type != "discussion":
        task += f"\nLegal `action` values: {json.dumps(choices)}"
    parts.append(f"YOUR TASK: {task}")
    if error:
        parts.append(f"Your previous answer was rejected: {error}")
    return "\n\n".join(parts)


def action_choices(view: PlayerView) -> tuple[list[str], dict[str, str]]:
    """Legal actions as names the model sees, and the map back to engine ids."""
    if not view.legal_actions:
        return [NO_ACTION], {NO_ACTION: NO_ACTION}
    names = {p.id: p.name for p in view.players}
    to_id = {(ABSTAIN if a == ABSTAIN else names[a]): a for a in view.legal_actions}
    return list(to_id), to_id
