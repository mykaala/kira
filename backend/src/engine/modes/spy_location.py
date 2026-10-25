"""Hidden location (working name spy_location): one spy, everyone else shares a secret location.
Players take turns asking each other questions; the spy may name the location on their own turn,
and a plurality vote ends the round. Inspired by Spyfall (Alexandr Ushan); the location list and
every text here are our own."""

import random
import re
from collections import Counter

from ..config import ModeConfig, PhaseSpec
from ..models import GameState, NewEvent, Outcome, PhaseType, Player, channel

SPY, CIVILIAN = "spy", "civilian"
CIVILIANS = "civilians"  # the team, and the channel that carries the location
GUESS = "guess:"  # a spy action is "guess:<location>"
ANSWER = "answer"
ASKS_PER_PLAYER = 2

# location -> words that name it outright (the location itself is always included)
LOCATIONS: dict[str, list[str]] = {
    "night market": [],
    "ferry": ["ferries"],
    "ski lodge": ["ski chalet"],
    "dentist office": ["dentist", "dentists", "dentist's", "dental office", "dental clinic"],
    "recording studio": ["recording booth"],
    "laundromat": ["laundrette", "laundromats"],
    "bowling alley": ["bowling"],
    "wedding reception": ["wedding"],
    "sleeper train": ["sleeper car", "train"],
    "film set": ["movie set", "film shoot", "movie shoot"],
    "aquarium": [],
    "fire station": ["firehouse", "fire hall"],
    "hot spring": ["hot springs", "onsen"],
    "public library": ["library"],
    "food truck rally": ["food truck", "food trucks"],
    "escape room": [],
    "vineyard": ["winery"],
    "planetarium": [],
    "car wash": [],
    "karaoke bar": ["karaoke"],
}
LOCATION_NAMES = list(LOCATIONS)

STOCK_QUESTIONS = [
    "what would you wear here?",
    "how did you get here today?",
    "what's the first thing you notice when you walk in?",
    "would you bring a kid here?",
    "how long do people usually stay?",
]
STOCK_ANSWER = "honestly depends on the day"

RULES = f"""\
Hidden location. One player is secretly the spy; everyone else is a civilian.
The civilians all know the same secret location, picked from the list below. The spy does not know it.
Players take turns. The asker picks another player and asks them one question, in public. The target answers
in public, then becomes the next asker. You can't ask the player who just asked you, unless nobody else is left.
Each player asks about {ASKS_PER_PLAYER} questions; when the questions run out, everyone votes for who they think
is the spy (you can't vote for yourself or abstain). Most votes is accused; a tie accuses nobody.
On their own turn to ask, the spy may instead name the location: right and the spy wins, wrong and the spy loses.
If the vote accuses the spy, the civilians win, but the spy first gets one last chance to name the location:
right and the spy wins after all. If the vote accuses a civilian, or ties, the spy wins.
Locations: {", ".join(LOCATION_NAMES)}."""


def _alias_rx(loc: str) -> re.Pattern:
    forms = sorted({loc, *LOCATIONS[loc]}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(f).replace(r"\ ", r"[\s-]+") for f in forms) + r")\b", re.I)


_ALIAS_RX = {loc: _alias_rx(loc) for loc in LOCATIONS}


def names_location(text: str, loc: str) -> bool:
    """The text names this location outright (its name or an alias), the thing civilians must not do."""
    return bool(_ALIAS_RX[loc].search(text))


# --- reading the game from its events --------------------------------------------------------


def location(state: GameState) -> str | None:
    e = next((e for e in state.events if e.kind == "location"), None)
    return e.text.removeprefix("The location is: ").removesuffix(".") if e else None


def spy(state: GameState) -> Player:
    return next(p for p in state.players if p.role == SPY)


def asks(state: GameState) -> list:
    return [e for e in state.events if e.kind == "ask"]


def exchange_cap(state: GameState) -> int:
    return ASKS_PER_PLAYER * len(state.players)


def asker(state: GameState) -> str | None:
    """Whose turn it is to ask: whoever answered last, or the first asker."""
    e = next((e for e in reversed(state.events) if e.kind in ("first", "answer")), None)
    return None if e is None else (e.target if e.kind == "first" else e.actor)


def answerer(state: GameState) -> str | None:
    e = next((e for e in reversed(state.events) if e.kind == "ask"), None)
    return e.target if e else None


def targets(state: GameState, p: Player) -> list[str]:
    """Who this asker may ask: anyone else with asks left (anyone else on the last exchange), but not
    the player who just asked them unless nobody else is left."""
    done = asks(state)
    count = Counter(e.actor for e in done)
    last = len(done) == exchange_cap(state) - 1
    pool = [q.id for q in state.players if q.id != p.id and (last or count[q.id] < ASKS_PER_PLAYER)]
    if done and done[-1].target == p.id and len(pool) > 1 and done[-1].actor in pool:
        pool.remove(done[-1].actor)
    return pool


def shortlist(state: GameState) -> list[str]:
    """The true location plus decoys, in a seeded order, for the last-chance guess."""
    rng = random.Random(f"{state.seed}:shortlist")
    loc = location(state)
    decoys = rng.sample([x for x in LOCATION_NAMES if x != loc], SPY_MODE.options["shortlist_size"] - 1)
    out = [loc, *decoys]
    rng.shuffle(out)
    return out


# --- the mode's functions ------------------------------------------------------------------------


def legal_actions(state: GameState, p: Player) -> list[str]:
    if state.winner:
        return []
    if state.phase == "ask" and p.id == asker(state):
        options = targets(state, p)
        if options and p.role == SPY:
            options += [GUESS + loc for loc in LOCATION_NAMES]
        return options
    if state.phase == "answer" and p.id == answerer(state):
        return [ANSWER]
    if state.phase == "vote":
        return [q.id for q in state.players if q.id != p.id]
    if state.phase == "last_chance" and p.role == SPY:
        guesses = shortlist(state) if SPY_MODE.options.get("last_chance_shortlist") else LOCATION_NAMES
        return [GUESS + loc for loc in guesses]
    return []


def default_action(state: GameState, p: Player, legal: list[str], rng: random.Random) -> str:
    """Ask someone, never guess; at the last chance (guesses only), a random guess."""
    plain = [a for a in legal if not a.startswith(GUESS)]
    return rng.choice(plain or legal)


def _outcome(winner: str, text: str) -> NewEvent:
    return NewEvent(kind="outcome", target=winner, text=text)


def _guess(state: GameState, pid: str, action: str, kind: str) -> list[NewEvent]:
    loc, truth = action.removeprefix(GUESS), location(state)
    name = state.player(pid).name
    right = loc == truth
    return [
        NewEvent(kind=kind, actor=pid, text=f"{name} is the spy and names the location: {loc}."),
        _outcome(
            SPY if right else CIVILIANS,
            f"The location was {truth}. " + ("Right: the spy wins." if right else "Wrong: the civilians win."),
        ),
    ]


def resolve_deal(state: GameState, actions: dict[str, str]) -> Outcome:
    loc = state.rng("location").choice(LOCATION_NAMES)
    first = state.rng("first").choice(state.players)
    return Outcome(
        events=[
            NewEvent(kind="location", vis=channel(CIVILIANS), text=f"The location is: {loc}."),
            NewEvent(kind="first", target=first.id, text=f"{first.name} asks first."),
        ]
    )


def resolve_ask(state: GameState, actions: dict[str, str]) -> Outcome:
    if not actions:
        return Outcome(events=[NewEvent(kind="info", text="Nobody is left to ask. Time to vote.")])
    ((pid, action),) = actions.items()
    if action.startswith(GUESS):
        return Outcome(events=_guess(state, pid, action, "guess"))
    text = state.submitted_text.get(pid) or state.rng("stock").choice(STOCK_QUESTIONS)
    return Outcome(events=[NewEvent(kind="ask", actor=pid, target=action, text=text)])


def resolve_answer(state: GameState, actions: dict[str, str]) -> Outcome:
    ((pid, _),) = actions.items()
    return Outcome(events=[NewEvent(kind="answer", actor=pid, text=state.submitted_text.get(pid) or STOCK_ANSWER)])


def resolve_vote(state: GameState, actions: dict[str, str]) -> Outcome:
    names = {p.id: p.name for p in state.players}
    events = [
        NewEvent(kind="vote", actor=pid, target=t, text=f"{names[pid]} voted for {names[t]}.")
        for pid, t in sorted(actions.items(), key=lambda kv: int(kv[0][1:]))
    ]
    counts = Counter(actions.values())
    top = max(counts.values())
    leaders = [t for t, c in counts.items() if c == top]
    the_spy, loc = spy(state), location(state)
    if len(leaders) > 1:
        events += [
            NewEvent(kind="accused", text="The vote is tied, so nobody is accused."),
            _outcome(SPY, f"The spy was {the_spy.name} and the location was {loc}. The spy wins."),
        ]
    elif leaders[0] != the_spy.id:
        events += [
            NewEvent(kind="accused", target=leaders[0], text=f"{names[leaders[0]]} is accused, and is not the spy."),
            _outcome(SPY, f"The spy was {the_spy.name} and the location was {loc}. The spy wins."),
        ]
    elif SPY_MODE.options.get("last_chance_guess"):
        events.append(
            NewEvent(
                kind="accused",
                target=the_spy.id,
                text=f"{the_spy.name} is accused, and is the spy! One last chance to name the location.",
            )
        )
    else:
        events += [
            NewEvent(kind="accused", target=the_spy.id, text=f"{the_spy.name} is accused, and is the spy!"),
            _outcome(CIVILIANS, f"The location was {loc}. The civilians win."),
        ]
    return Outcome(events=events)


def resolve_last_chance(state: GameState, actions: dict[str, str]) -> Outcome:
    ((pid, action),) = actions.items()
    return Outcome(events=_guess(state, pid, action, "last_guess"))


def win_check(state: GameState) -> str | None:
    return next((e.target for e in reversed(state.events) if e.kind == "outcome"), None)


def next_phase(state: GameState) -> str:
    if state.phase == "deal":
        return "ask"
    if state.phase == "ask":
        return "answer" if state.events[-1].kind == "ask" else "vote"
    if state.phase == "answer":
        return "vote" if len(asks(state)) >= exchange_cap(state) else "ask"
    return "last_chance"  # after a vote that accused the spy; every other ending is decided


def intent(state: GameState, p: Player) -> dict | None:
    """A seeded private plan for this turn. The spy blends in, or gets a window to name the location
    (likelier as the round goes on, and always on their last ask); a civilian probes or stays vague."""
    up = (state.phase == "ask" and p.id == asker(state)) or (state.phase == "answer" and p.id == answerer(state))
    if not up or state.winner:
        return None
    o = SPY_MODE.options
    done = asks(state)
    rng = random.Random(f"{state.seed}:intent:{p.id}:{state.phase}:{len(done)}")
    if p.role == SPY:
        if state.phase == "ask":
            mine = sum(e.actor == p.id for e in done)
            last = mine >= ASKS_PER_PLAYER - 1 or len(done) >= exchange_cap(state) - 1
            chance = o["spy_guess_base"] + o["spy_guess_slope"] * len(done) / exchange_cap(state)
            if last or rng.random() < chance:
                return {"plan": "guess_window"}
        return {"plan": "blend"}
    return {"plan": "probe" if rng.random() < o["civilian_probe"] else "vague"}


SPY_MODE = ModeConfig(
    name="spy_location",
    title="Hidden Location",
    rules=RULES,
    min_players=5,
    max_players=8,
    roles_by_count={n: {SPY: 1, CIVILIAN: n - 1} for n in range(5, 9)},
    teams={SPY: SPY, CIVILIAN: CIVILIANS},
    channels={CIVILIANS: [CIVILIAN]},
    teammates_visible=[],
    phases={
        "deal": PhaseSpec(name="deal", type=PhaseType.AUTOMATIC),
        "ask": PhaseSpec(name="ask", type=PhaseType.SIMULTANEOUS),
        "answer": PhaseSpec(name="answer", type=PhaseType.SIMULTANEOUS),
        "vote": PhaseSpec(name="vote", type=PhaseType.SIMULTANEOUS),
        "last_chance": PhaseSpec(name="last_chance", type=PhaseType.SIMULTANEOUS),
    },
    first_phase="deal",
    new_day_phase="deal",
    transitions={"deal": "ask", "ask": "answer", "answer": "ask", "vote": "last_chance"},  # see next_phase
    next_phase=next_phase,
    options={
        "last_chance_guess": True,  # a spy caught by the vote may still name the location
        "last_chance_shortlist": False,  # ...from a short list (true location plus decoys), not all 20
        "shortlist_size": 5,
        "spy_guess_base": 0.05,  # the spy's chance of a guess window on an ask turn, plus slope x progress
        "spy_guess_slope": 0.35,
        "civilian_probe": 0.6,  # a civilian's chance to probe rather than stay vague, per turn
    },
    legal_actions=legal_actions,
    resolvers={
        "deal": resolve_deal,
        "ask": resolve_ask,
        "answer": resolve_answer,
        "vote": resolve_vote,
        "last_chance": resolve_last_chance,
    },
    default_action=default_action,
    win_check=win_check,
    intent=intent,
)
