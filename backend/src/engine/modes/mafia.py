"""Mafia: plurality voting under hidden information."""

import random
import re
from collections import Counter

from ..config import ModeConfig, PhaseSpec
from ..models import ABSTAIN, ClaimIn, GameState, NewEvent, Outcome, PhaseType, Player, channel, private

MAFIA, VILLAGER, DETECTIVE, DOCTOR = "mafia", "villager", "detective", "doctor"
JESTER, BODYGUARD = "jester", "bodyguard"  # optional roles, each replacing a villager

RULES = """\
Mafia. Players are secretly villagers, a detective, a doctor, or mafia.
The mafia know each other; nobody else knows anyone's role.
Each night the mafia choose someone to kill, the doctor protects one player (themselves allowed, but never
the same player two nights in a row), and the detective learns whether one player is mafia.
Each day everyone discusses, then votes to eliminate one player. Most votes is eliminated;
a tie, or more abstains than votes for anyone, eliminates nobody. An eliminated player's role is revealed.
The village wins when every mafia member is gone. The mafia win when they equal or outnumber everyone else.
Optional roles, only if this game deals them:
- Jester: wins alone, at once, if the town votes them out. Otherwise they lose.
- Bodyguard: each night guards one other player. If the mafia attack that player, the bodyguard dies instead."""


def _roles(n: int) -> dict[str, int]:
    mafia = 1 if n <= 6 else 2
    return {MAFIA: mafia, DETECTIVE: 1, DOCTOR: 1, VILLAGER: n - mafia - 2}


def legal_actions(state: GameState, p: Player) -> list[str]:
    if not p.alive or state.winner:
        return []
    others = [q.id for q in state.alive() if q.id != p.id]
    if state.phase == "night":
        if p.role == MAFIA:
            if state.day == 1 and MAFIA_MODE.options.get("skip_first_night_kill"):
                return []
            return [q.id for q in state.alive() if q.role != MAFIA]
        if p.role == DOCTOR:
            return [q.id for q in state.alive() if q.id != _last_protected(state, p)] + [ABSTAIN]
        if p.role in (DETECTIVE, BODYGUARD):
            return others + [ABSTAIN]
        return []
    if state.phase == "vote":
        return others + [ABSTAIN]
    return []


def _last_protected(state: GameState, p: Player) -> str | None:
    """Last night's save, if the doctor may not repeat it. Night 1 doesn't count when the mafia
    can't kill on it: that save protected nobody."""
    if not MAFIA_MODE.options.get("doctor_no_repeat"):
        return None
    if state.day == 2 and MAFIA_MODE.options.get("skip_first_night_kill"):
        return None
    return next(
        (
            e.target
            for e in reversed(state.events)
            if e.kind == "result" and e.vis == private(p.id) and e.day == state.day - 1 and e.phase == "night"
        ),
        None,
    )


def default_action(state: GameState, p: Player, legal: list[str], rng: random.Random) -> str:
    if ABSTAIN in legal:
        return ABSTAIN
    return rng.choice(legal)


def _plurality(votes: list[str], rng: random.Random | None = None) -> str | None:
    """Most-voted target. Ties go to `rng` if given, otherwise nobody."""
    counts = Counter(v for v in votes if v != ABSTAIN)
    if not counts:
        return None
    top = max(counts.values())
    leaders = sorted(t for t, c in counts.items() if c == top)
    if len(leaders) == 1:
        return leaders[0]
    return rng.choice(leaders) if rng else None


def resolve_night(state: GameState, actions: dict[str, str]) -> Outcome:
    out = Outcome()
    name = lambda pid: state.player(pid).name  # noqa: E731
    by_role = lambda role: [pid for pid, a in actions.items() if state.player(pid).role == role]  # noqa: E731

    target = _plurality([actions[pid] for pid in by_role(MAFIA)], state.rng("mafia-tiebreak"))
    saved = {actions[pid] for pid in by_role(DOCTOR)} - {ABSTAIN}

    if target:
        out.events.append(
            NewEvent(kind="mafia_choice", text=f"The mafia chose {name(target)}.", vis=channel(MAFIA), target=target)
        )
    for pid in by_role(DETECTIVE):
        checked = actions[pid]
        if checked != ABSTAIN:
            is_mafia = state.player(checked).role == MAFIA
            out.events.append(
                NewEvent(
                    kind="result",
                    vis=private(pid),
                    target=checked,
                    text=f"Your investigation: {name(checked)} is {'MAFIA' if is_mafia else 'not mafia'}.",
                )
            )
    for pid in by_role(DOCTOR):
        if actions[pid] != ABSTAIN:
            out.events.append(
                NewEvent(
                    kind="result",
                    vis=private(pid),
                    target=actions[pid],
                    text=f"You protected {name(actions[pid])} tonight.",
                )
            )
    guarded = {actions[pid]: pid for pid in by_role(BODYGUARD) if actions[pid] != ABSTAIN}
    for target_id, pid in guarded.items():
        out.events.append(
            NewEvent(kind="result", vis=private(pid), target=target_id, text=f"You guarded {name(target_id)} tonight.")
        )

    # deaths are announced publicly by the morning resolver
    if target and target not in saved:
        out.deaths.append(guarded.get(target, target))  # a bodyguard takes the hit
    return out


def _death_text(state: GameState, pid: str, how: str) -> str:
    p = state.player(pid)
    reveal = f" They were a {p.role}." if MAFIA_MODE.reveal_role_on_death else ""
    return f"{p.name} {how}.{reveal}"


def resolve_vote(state: GameState, actions: dict[str, str]) -> Outcome:
    out = Outcome()
    name = lambda pid: state.player(pid).name  # noqa: E731
    for pid in sorted(actions, key=lambda x: [p.id for p in state.players].index(x)):
        a = actions[pid]
        text = f"{name(pid)} abstained." if a == ABSTAIN else f"{name(pid)} voted for {name(a)}."
        out.events.append(NewEvent(kind="vote", actor=pid, target=None if a == ABSTAIN else a, text=text))

    votes = list(actions.values())
    target = _plurality(votes)
    abstains = votes.count(ABSTAIN)
    if target and Counter(votes)[target] > abstains:
        out.deaths.append(target)
        out.events.append(
            NewEvent(kind="elimination", target=target, text=_death_text(state, target, "was eliminated"))
        )
    else:
        out.events.append(NewEvent(kind="elimination", text="No one was eliminated."))
    return out


def resolve_morning(state: GameState, actions: dict[str, str]) -> Outcome:
    """The day's first public line: who died in the night."""
    deaths = [_death_text(state, pid, "was killed in the night") for pid in state.last_deaths]
    quiet = "Day 1 begins. No one has died yet." if state.day == 1 else "No one died."
    return Outcome(
        events=[
            NewEvent(
                kind="morning",
                text=" ".join(deaths) or quiet,
                target=state.last_deaths[0] if state.last_deaths else None,
            )
        ]
    )


def resolve_discussion(state: GameState, actions: dict[str, str]) -> Outcome:
    return Outcome()


def _checks(state: GameState, p: Player) -> dict[str, str]:
    """A detective's results so far: target id -> "mafia" | "not mafia"."""
    if p.role != DETECTIVE:
        return {}
    return {
        e.target: "mafia" if state.player(e.target).role == MAFIA else "not mafia"
        for e in state.events
        if e.kind == "result" and e.vis == private(p.id) and e.target
    }


def judge_claim(state: GameState, p: Player, claim: ClaimIn) -> tuple[str | None, bool]:
    """Anyone may claim anything, except that the real detective can only report real results."""
    if claim.result is not None:
        if claim.role != DETECTIVE or claim.target is None:
            return "only a detective claim can have a result, and it needs a target", False
        if claim.result not in ("mafia", "not mafia"):
            return "a result is either 'mafia' or 'not mafia'", False
    if p.role == DETECTIVE and claim.role == DETECTIVE and claim.target is not None:
        checks = _checks(state, p)
        name = state.player(claim.target).name
        got = ", ".join(f"{state.player(t).name}: {r}" for t, r in checks.items()) or "none yet"
        if claim.target not in checks:
            return f"you never checked {name}. Your real results: {got}", False
        if claim.result is not None and claim.result != checks[claim.target]:
            return f"your check on {name} came back {checks[claim.target]}. Your real results: {got}", False
    return None, p.role == claim.role


def mafia_intent(state: GameState, p: Player) -> dict | None:
    """Today's team plan for a mafia player, rolled from the seed and the day (probabilities in
    the mode options): blend in, fake-claim detective with a made-up result, or counterclaim an
    existing detective claim; and at the vote, whether the team splits."""
    if p.role != MAFIA or not p.alive or state.winner or state.phase not in ("discussion", "vote", "night"):
        return None
    opts = MAFIA_MODE.options
    team = [q.id for q in state.players if q.role == MAFIA and q.alive]
    partners = [t for t in team if t != p.id]
    if state.phase == "night":
        target = kill_target(state, team) if legal_actions(state, p) else None
        return {"talk": "night", "partners": partners, "kill": target} if target else None
    rng = random.Random(f"{state.seed}:mafia-intent:{state.day}")
    claimer, roll_claim, roll_split = rng.choice(team), rng.random(), rng.random()

    plan: dict = {"talk": "blend", "partners": partners}
    det_claims = [c for c in state.claims if c.role == DETECTIVE]
    ours = [c for c in det_claims if c.actor in team]
    theirs = [c for c in det_claims if c.actor not in team and state.player(c.actor).alive]
    # only a claim that names one of us as mafia is worth fighting; a claim that clears someone is left alone
    against_us = [c for c in theirs if c.result == "mafia" and c.target in team]
    if ours:  # someone on the team already claimed: they keep the story, the rest blend
        if any(c.actor == p.id for c in ours):
            plan["talk"] = "keep_claim"
    elif theirs:
        if against_us and roll_claim < opts["counterclaim_p"] and p.id == claimer:
            plan.update(
                talk="counterclaim", claim={"role": DETECTIVE, "target": against_us[0].actor, "result": "mafia"}
            )
    elif roll_claim < opts["fake_claim_p"].get(state.day, opts["fake_claim_p_later"]) and p.id == claimer:
        # the made-up result is about a living player whose role is not public
        living = [q.id for q in state.alive() if q.id != p.id]
        live_partners = [t for t in partners if t in living]
        if live_partners and rng.random() < opts["clear_partner_p"]:
            plan.update(
                talk="fake_claim", claim={"role": DETECTIVE, "target": rng.choice(live_partners), "result": "not mafia"}
            )
        else:
            others = [q for q in living if q not in team]
            plan.update(talk="fake_claim", claim={"role": DETECTIVE, "target": rng.choice(others), "result": "mafia"})
    if len(team) > 1:
        split = roll_split < opts["split_vote_p"]
        plan["vote"] = ("follow" if p.id == team[0] else "own") if split else "free"
    return plan


def kill_target(state: GameState, team: list[str]) -> tuple[str, str] | None:
    """Who the mafia should kill tonight, and why: a living player who claimed detective (the
    latest claim), else the one the town trusts most (cleared by a detective claim, then fewest
    votes against them all game). Ties are seeded."""
    living = [q.id for q in state.alive() if q.id not in team]
    if not living:
        return None
    claimed = [c.actor for c in state.claims if c.role == DETECTIVE and c.actor in living]
    if claimed:
        return claimed[-1], "claimed detective"
    cleared = [c.target for c in state.claims if c.role == DETECTIVE and c.result == "not mafia" and c.target in living]
    if cleared:
        return cleared[-1], "was cleared by a detective claim"
    votes = Counter(e.target for e in state.events if e.kind == "vote" and e.target)
    rng = random.Random(f"{state.seed}:kill-target:{state.day}")
    order = sorted(living, key=lambda q: (votes[q], rng.random()))
    return order[0], "is the player the town trusts most (fewest votes against them)"


def _named_today(state: GameState, p: Player) -> bool:
    """Someone else has said this player's name in today's discussion."""
    name = re.compile(rf"\b{re.escape(p.name)}\b", re.I)
    return any(e.kind == "say" and e.day == state.day and e.actor != p.id and name.search(e.text) for e in state.events)


def detective_intent(state: GameState, p: Player) -> dict | None:
    """When the real detective holding a mafia result reveals it: on day 1 only some of the
    time (the rest wait until day 2, or until someone names them), always from day 2."""
    if state.phase != "discussion" or any(c.actor == p.id and c.role == DETECTIVE for c in state.claims):
        return None
    hits = [t for t, r in _checks(state, p).items() if r == "mafia" and state.player(t).alive]
    if not hits:
        return None
    rng = random.Random(f"{state.seed}:detective-intent")
    early = rng.random() < MAFIA_MODE.options["detective_day1_claim_p"]
    if state.day >= 2 or early or _named_today(state, p):
        return {"talk": "reveal", "claim": {"role": DETECTIVE, "target": hits[0], "result": "mafia"}}
    return {"talk": "hold"}


def intent(state: GameState, p: Player) -> dict | None:
    if not p.alive or state.winner:
        return None
    if p.role == MAFIA:
        return mafia_intent(state, p)
    if p.role == DETECTIVE:
        return detective_intent(state, p)
    return None


def win_check(state: GameState) -> str | None:
    if any(e.kind == "elimination" and e.target and state.player(e.target).role == JESTER for e in state.events):
        return "jester"
    alive = state.alive()
    mafia = sum(p.role == MAFIA for p in alive)
    if mafia == 0:
        return "village"
    if mafia >= len(alive) - mafia:
        return "mafia"
    return None


MAFIA_MODE = ModeConfig(
    name="mafia",
    title="Mafia",
    rules=RULES,
    rules_roles_hidden=RULES.replace(
        "An eliminated player's role is revealed.",
        "Roles stay secret until the game ends: an eliminated or killed player's role is NOT revealed.",
    ),
    min_players=5,
    max_players=9,
    roles_by_count={n: _roles(n) for n in range(5, 10)},
    teams={
        MAFIA: "mafia",
        VILLAGER: "village",
        DETECTIVE: "village",
        DOCTOR: "village",
        JESTER: "jester",
        BODYGUARD: "village",
    },
    optional_roles=[JESTER, BODYGUARD],
    channels={MAFIA: [MAFIA]},
    teammates_visible=[MAFIA],
    phases={
        "night": PhaseSpec(name="night", type=PhaseType.SIMULTANEOUS),
        "morning": PhaseSpec(name="morning", type=PhaseType.AUTOMATIC),
        "discussion": PhaseSpec(name="discussion", type=PhaseType.SEQUENTIAL, rounds=2, extra_speakers=3),
        "vote": PhaseSpec(name="vote", type=PhaseType.SIMULTANEOUS),
    },
    first_phase="night",
    new_day_phase="night",
    transitions={"night": "morning", "morning": "discussion", "discussion": "vote", "vote": "night"},
    reveal_role_on_death=False,  # roles are shown only when the game ends
    options={
        "skip_first_night_kill": True,
        "doctor_no_repeat": True,  # the doctor can't protect the same player two nights running
        # the mafia's daily plan (first guesses, tune from self-play)
        "fake_claim_p": {1: 0.5},  # by day: one mafia fake-claims detective
        "fake_claim_p_later": 0.15,
        "counterclaim_p": 0.25,  # only against a detective claim that names one of the team as mafia
        "detective_day1_claim_p": 0.5,  # a detective with a mafia result reveals on day 1; else day 2 or when named
        "clear_partner_p": 0.25,  # a fake result clears the partner instead of accusing a villager
        "split_vote_p": 0.6,  # the team deliberately votes apart
    },
    legal_actions=legal_actions,
    resolvers={
        "night": resolve_night,
        "morning": resolve_morning,
        "discussion": resolve_discussion,
        "vote": resolve_vote,
    },
    default_action=default_action,
    win_check=win_check,
    claimable_roles=[DETECTIVE, DOCTOR, VILLAGER, BODYGUARD],
    clear_accusations_after=["vote"],
    judge_claim=judge_claim,
    intent=intent,
)
