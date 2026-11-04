"""Out of Place (code name spy_location): one spy, everyone else shares a secret location. Players take
turns asking each other questions, in rounds; the spy may name the location at any point while questions are
asked, on anyone's turn. Each round ends
in a plurality vote: a caught spy gets a last chance, a wrongly accused civilian is out, and the spy wins after
surviving enough votes. Credits for the borrowed mechanic are in
docs/design.md; the location list and every text here are our own."""

import random
import re
from collections import Counter

from ..config import ModeConfig, PhaseSpec
from ..models import GameState, NewEvent, Outcome, PhaseType, Player, channel, private
from .spy_roles import ROLES

TITLE = "Out of Place"  # the name shown to players
SPY, CIVILIAN = "spy", "civilian"
CIVILIANS = "civilians"  # the team, and the channel that carries the location
DRAW = "draw"  # a game outcome that is neither side's win
GUESS = "guess:"  # a spy action is "guess:<location>"
GUESS_MISS = GUESS + "-"  # the spy named a place, in its own words, that the server ruled is not the location
ANSWER = "answer"
PLACE_ROLE = "place_role"  # a civilian's private role at the location (the `roles` option)
ROLE_CARD = ("title", "wears", "does", "deals_with")  # what a player sees of their role; never `insider_tell`
ANGLES = ["what they wear", "the tools or things they use", "who they deal with", "a typical problem they run into"]

# cluster -> location -> words that name it outright (the location itself is always included). Places in a
# cluster share several features, so a vague answer fits the whole cluster.
CLUSTERS: dict[str, dict[str, list[str]]] = {
    "crowded, food, outdoors at night": {
        "night market": ["night markets"],
        "food truck rally": ["food truck", "food trucks"],
        "county fair": ["fairground", "fairgrounds", "state fair"],
        "street festival": ["street fest", "street fair", "block party"],
    },
    "dim, quiet, seated, watching": {
        "planetarium": ["planetariums", "planetaria"],
        "cinema": ["movie theater", "movie theatre", "multiplex"],
        "opera house": ["opera"],
        "lecture hall": ["lecture theatre", "lecture theater"],
    },
    "hot and wet": {
        "hot spring": ["hot springs", "onsen"],
        "sauna": ["saunas", "steam room"],
        "swimming pool": ["pool", "swimming baths"],
        "water park": ["waterpark", "water parks"],
    },
    "cold and snowy": {
        "ski lodge": ["ski chalet"],
        "ice rink": ["skating rink", "ice skating rink"],
        "mountain hut": ["alpine hut", "mountain refuge"],
        "ice fishing camp": ["ice fishing"],
    },
    "transport, sitting for hours": {
        "ferry": ["ferries"],
        "overnight bus": ["night bus", "overnight coach"],
        "cable car": ["cable cars", "gondola"],
        "airport lounge": ["airport"],
    },
    "loud, music, games, rented shoes": {
        "karaoke bar": ["karaoke"],
        "bowling alley": ["bowling"],
        "roller rink": ["roller skating", "roller disco"],
        "video arcade": ["arcade", "arcades"],
    },
    "appointments and waiting rooms": {
        "dentist office": ["dentist", "dentists", "dentist's", "dental office", "dental clinic"],
        "hair salon": ["salon", "hairdresser", "hairdresser's", "barbershop"],
        "vet clinic": ["vet", "vets", "vet's", "veterinarian", "animal hospital"],
        "passport office": ["passport agency"],
    },
    "errands and chores": {
        "laundromat": ["laundrette", "laundromats"],
        "car wash": ["carwash"],
        "post office": ["post offices"],
        "hardware store": ["hardware shop"],
    },
    "nature behind glass or on paths": {
        "aquarium": ["aquariums", "aquaria"],
        "botanical garden": ["botanical gardens", "botanic garden"],
        "butterfly house": ["butterfly garden"],
        "nature reserve": ["nature preserve", "wildlife reserve"],
    },
    "media production": {
        "recording studio": ["recording booth"],
        "radio station": ["radio studio"],
        "photo studio": ["photography studio", "photo shoot"],
        "tv newsroom": ["newsroom", "news studio"],
    },
}
LOCATIONS: dict[str, list[str]] = {loc: aliases for places in CLUSTERS.values() for loc, aliases in places.items()}
CLUSTER_OF = {loc: name for name, places in CLUSTERS.items() for loc in places}
LOCATION_NAMES = sorted(LOCATIONS)  # one fixed order for the rules and every enum: no cluster hints

STOCK_QUESTIONS = [
    "what would you wear here?",
    "how did you get here today?",
    "what's the first thing you notice when you walk in?",
    "would you bring a kid here?",
    "how long do people usually stay?",
]
STOCK_ANSWER = "honestly depends on the day"


def rules_text(options: dict) -> str:
    """The rules every agent reads, matching this game's switches."""
    right = "the game is a draw" if options.get("last_chance_result") == "draw" else "the spy wins after all"
    caught = (
        "If the vote accuses the spy, the civilians win, but the spy first gets one last chance to name the location:\n"
        f"right and {right}."
        if options.get("last_chance_guess")
        else "If the vote accuses the spy, the civilians win."
    )
    tie = (
        "on a tie, everyone votes once more between the tied players only, and a second tie accuses nobody"
        if options.get("tie_revote")
        else "a tie accuses nobody"
    )
    n = options.get("asks_per_player", 2)
    asks = {1: "one question", 2: "two questions", 3: "three questions"}.get(n, f"{n} questions")
    k = options.get("spy_survive_votes", 1)
    if k == 1:
        survive = "If the vote accuses a civilian, or ties, the spy wins."
    else:
        times = {2: "two votes", 3: "three votes"}.get(k, f"{k} votes")
        survive = (
            "If the vote accuses a civilian, that player is out of the game and everyone learns they were a "
            "civilian; if it ties, nobody is out. Either way the spy has survived a vote, and a new round starts "
            f"with the players still in. The spy wins after surviving {times}, or as soon as only the spy and "
            "one civilian are left."
        )
    rnd = "In each round, each player still in asks" if k > 1 else "Each player asks"
    roles = (
        "\nEvery civilian also has a secret role at the location (for example a staff member or a visitor), and "
        "civilians' roles differ. The spy has no role."
        if options.get("roles")
        else ""
    )
    return f"""\
Hidden location. One player is secretly the spy; everyone else is a civilian.
The civilians all know the same secret location. The spy does not know it.
Players take turns. The asker picks another player and asks them one question, in public. The target answers
in public, then becomes the next asker. You can't ask the player who just asked you, unless nobody else is left.
{rnd} about {asks}; when the questions run out, everyone votes for who they think
is the spy (you can't vote for yourself or abstain). Most votes is accused; {tie}.
At any point during the questions, on anyone's turn, the spy may reveal themselves and name the location: right
and the spy wins, wrong and the spy loses.
{caught} {survive}{roles}"""


def _alias_rx(loc: str) -> re.Pattern:
    forms = sorted({loc, *LOCATIONS[loc]}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(f).replace(r"\ ", r"[\s-]+") for f in forms) + r")\b", re.I)


_ALIAS_RX = {loc: _alias_rx(loc) for loc in LOCATIONS}


def names_location(text: str, loc: str) -> bool:
    """The text names this location outright (its name or an alias), the thing civilians must not do."""
    return bool(_ALIAS_RX[loc].search(text))


def names_title(text: str, title: str) -> bool:
    """The text says this role title (word for word, spaces or hyphens between words, an optional plural)."""
    rx = re.escape(title).replace(r"\ ", r"[\s-]+").replace(r"\-", r"[\s-]*")
    return bool(re.search(rf"\b{rx}s?\b", text, re.I))


# --- reading the game from its events --------------------------------------------------------


def location(state: GameState) -> str | None:
    e = next((e for e in state.events if e.kind == "location"), None)
    return e.text.removeprefix("The location is: ").removesuffix(".") if e else None


def place_role(state: GameState, pid: str) -> dict | None:
    """This civilian's role card at the location (roles on), without the insider tell; None for the spy."""
    e = next((e for e in state.events if e.kind == PLACE_ROLE and e.target == pid), None)
    if e is None:
        return None
    card = next(r for r in ROLES[location(state)] if r["title"] == e.text)
    return {k: card[k] for k in ROLE_CARD}


def deal_roles(seed: int, place: str, civilians: list[str], min_generic: int) -> dict[str, str]:
    """A distinct role title for each civilian, seeded (seed + "roles"): at least `min_generic` generic roles, the
    rest drawn from the whole bank for the place. Never fails: a place with fewer generic roles than the floor
    uses all it has (see generic_shortfall), and if the bank ran out, the last civilians would get no role."""
    rng = random.Random(f"{seed}:roles")
    bank = ROLES.get(place, [])
    generic = [r for r in bank if r["generic"]]
    picked = rng.sample(generic, min(max(0, min_generic), len(civilians), len(generic)))
    rest = [r for r in bank if r not in picked]
    picked += rng.sample(rest, min(len(civilians) - len(picked), len(rest)))
    rng.shuffle(picked)
    return {pid: r["title"] for pid, r in zip(civilians, picked)}


def generic_shortfall(place: str, civilians: int, min_generic: int) -> int:
    """How many generic roles short of the floor this place's deal falls (0 when the bank has enough)."""
    want = min(max(0, min_generic), civilians)
    return max(0, want - sum(r["generic"] for r in ROLES.get(place, [])))


def spy(state: GameState) -> Player:
    return next(p for p in state.players if p.role == SPY)


def asks(state: GameState) -> list:
    return [e for e in state.events if e.kind == "ask"]


def _round_start(state: GameState) -> int:
    """The index of the event that opened the current round (the deal's or the last vote's "first")."""
    return next((i for i in range(len(state.events) - 1, -1, -1) if state.events[i].kind == "first"), 0)


def round_events(state: GameState) -> list:
    return state.events[_round_start(state) :]


def round_asks(state: GameState) -> list:
    return [e for e in round_events(state) if e.kind == "ask"]


def round_no(state: GameState) -> int:
    """1 for the first round of questions, then one more after every vote the spy survives."""
    return max(1, sum(e.kind == "first" for e in state.events))


def votes_survived(state: GameState) -> int:
    return sum(e.kind == "survived" for e in state.events)


def opt(state: GameState, key: str):
    """One switch for this game: its own (set when it was created), else the mode's."""
    return state.options.get(key, SPY_MODE.options.get(key))


def survive_votes(state: GameState) -> int:
    return opt(state, "spy_survive_votes")


def asks_per_player(state: GameState) -> int:
    return opt(state, "asks_per_player")


def exchange_cap(state: GameState) -> int:
    """Questions in the current round: so many for each player still in."""
    return asks_per_player(state) * len(state.alive())


def asker(state: GameState) -> str | None:
    """Whose turn it is to ask: whoever answered last, or the first asker."""
    e = next((e for e in reversed(state.events) if e.kind in ("first", "answer")), None)
    return None if e is None else (e.target if e.kind == "first" else e.actor)


def answerer(state: GameState) -> str | None:
    e = next((e for e in reversed(state.events) if e.kind == "ask"), None)
    return e.target if e else None


def targets(state: GameState, p: Player) -> list[str]:
    """Who this asker may ask, among the players still in. Within a voting round questions go in passes: in
    pass r, only players who haven't asked r times yet, so everyone asks once per pass and the chain can't get
    stuck. A pass's last asker may ask anyone (they open the next pass), and so may the round's last asker;
    never the player who just asked them unless nobody else is left."""
    done = round_asks(state)
    count = Counter(e.actor for e in done)
    alive = state.alive()
    rnd = len(done) // len(alive) + 1  # the pass this ask belongs to
    pool = [q.id for q in alive if q.id != p.id and count[q.id] < rnd]
    if not pool:  # the last ask of a pass (or of the round)
        pool = [q.id for q in alive if q.id != p.id]
    if done and done[-1].target == p.id and len(pool) > 1 and done[-1].actor in pool:
        pool.remove(done[-1].actor)
    return pool


def shortlist(state: GameState) -> list[str]:
    """The true location plus decoys, in a seeded order, for the last-chance guess."""
    rng = random.Random(f"{state.seed}:shortlist")
    loc = location(state)
    decoys = rng.sample([x for x in LOCATION_NAMES if x != loc], opt(state, "shortlist_size") - 1)
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
            options += [GUESS + loc for loc in LOCATION_NAMES] + [GUESS_MISS]
        return options
    if state.phase == "answer" and p.id == answerer(state):
        return [ANSWER]
    if state.phase == "vote":
        return [q.id for q in state.alive() if q.id != p.id]
    if state.phase == "revote":
        return [t for t in tied_players(state) if t != p.id]
    if state.phase == "last_chance" and p.role == SPY:
        guesses = shortlist(state) if opt(state, "last_chance_shortlist") else LOCATION_NAMES
        return [GUESS + loc for loc in guesses] + [GUESS_MISS]
    return []


def interrupt_actions(state: GameState, p: Player) -> list[str]:
    """The spy may name the location out of turn, at any point during the questions."""
    if state.winner or state.phase not in ("ask", "answer") or p.role != SPY or not p.alive:
        return []
    return [GUESS + loc for loc in LOCATION_NAMES] + [GUESS_MISS]


def default_action(state: GameState, p: Player, legal: list[str], rng: random.Random) -> str:
    """Ask someone, never guess; at the last chance (guesses only), a miss: no valid guess."""
    plain = [a for a in legal if not a.startswith(GUESS)]
    return rng.choice(plain) if plain else GUESS_MISS


def _outcome(winner: str, text: str) -> NewEvent:
    return NewEvent(kind="outcome", target=winner, text=text)


def _guess(state: GameState, pid: str, action: str, kind: str) -> list[NewEvent]:
    """`action` carries the server's ruling (the location, or GUESS_MISS); the submitted text, if any, is the
    spy's own words, which are what the table sees."""
    loc, truth = action.removeprefix(GUESS), location(state)
    name = state.player(pid).name
    right = loc == truth
    said = state.submitted_text.get(pid) or (loc if action != GUESS_MISS else "nothing valid")
    return [
        NewEvent(kind=kind, actor=pid, text=f"{name} is the spy and names the location: {said}."),
        _outcome(DRAW, f"The location was {truth}. Right, so it's a draw.")
        if right and kind == "last_guess" and opt(state, "last_chance_result") == "draw"
        else _outcome(
            SPY if right else CIVILIANS,
            f"The location was {truth}. " + ("Right: the spy wins." if right else "Wrong: the civilians win."),
        ),
    ]


def resolve_deal(state: GameState, actions: dict[str, str]) -> Outcome:
    loc = state.rng("location").choice(LOCATION_NAMES)
    first = state.rng("first").choice(state.players)
    roles = []
    if opt(state, "roles"):
        civilians = [p.id for p in state.players if p.role == CIVILIAN]
        dealt = deal_roles(state.seed, loc, civilians, opt(state, "min_generic_roles_per_game"))
        roles = [NewEvent(kind=PLACE_ROLE, vis=private(pid), target=pid, text=t) for pid, t in dealt.items()]
    return Outcome(
        events=[
            NewEvent(kind="location", vis=channel(CIVILIANS), text=f"The location is: {loc}."),
            *roles,
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
    ((pid, action),) = actions.items()
    if action.startswith(GUESS):  # the spy named the location instead of letting the answer come
        return Outcome(events=_guess(state, pid, action, "guess"))
    return Outcome(events=[NewEvent(kind="answer", actor=pid, text=state.submitted_text.get(pid) or STOCK_ANSWER)])


def tied_players(state: GameState) -> list[str]:
    """The players this round's first vote tied between (the revote's only candidates), in seat order."""
    votes = [e.target for e in round_events(state) if e.kind == "vote" and e.phase == "vote"]
    counts = Counter(votes)
    top = max(counts.values(), default=0)
    return sorted((t for t, c in counts.items() if c == top), key=lambda pid: int(pid[1:])) if votes else []


def resolve_vote(state: GameState, actions: dict[str, str]) -> Outcome:
    """The vote; also the revote, where a tie is final."""
    names = {p.id: p.name for p in state.players}
    events = [
        NewEvent(kind="vote", actor=pid, target=t, text=f"{names[pid]} voted for {names[t]}.")
        for pid, t in sorted(actions.items(), key=lambda kv: int(kv[0][1:]))
    ]
    counts = Counter(actions.values())
    top = max(counts.values())
    leaders = [t for t, c in counts.items() if c == top]
    the_spy, loc = spy(state), location(state)
    if len(leaders) > 1 and state.phase == "vote" and opt(state, "tie_revote"):
        tied = sorted(leaders, key=lambda pid: int(pid[1:]))
        return Outcome(
            events=events
            + [
                NewEvent(
                    kind="accused",
                    text=f"The vote is tied between {', '.join(names[t] for t in tied)}. "
                    "One more vote, between them only.",
                )
            ]
        )
    if len(leaders) > 1:
        events.append(
            NewEvent(
                kind="accused",
                text="The vote is tied again, so nobody is accused."
                if state.phase == "revote"
                else "The vote is tied, so nobody is accused.",
            )
        )
        return _survived(state, events, out=None)
    elif leaders[0] != the_spy.id:
        out = leaders[0]
        events.append(NewEvent(kind="accused", target=out, text=f"{names[out]} is voted out, and was a civilian."))
        return _survived(state, events, out=out)
    elif opt(state, "last_chance_guess"):
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


def _survived(state: GameState, events: list[NewEvent], out: str | None) -> Outcome:
    """The vote missed the spy: `out` (a civilian, or nobody on a tie) leaves the game. The spy wins after
    surviving enough votes, or when only the spy and one civilian are left; otherwise a new round starts."""
    the_spy, loc = spy(state), location(state)
    k, survived = survive_votes(state), votes_survived(state) + 1
    alive = [p for p in state.alive() if p.id != out]
    events.append(
        NewEvent(
            kind="survived",
            text="The spy survived the vote." if k == 1 else f"The spy has survived {survived} of {k} votes.",
        )
    )
    deaths = [out] if out else []
    if survived >= k or len(alive) <= 2:
        why = "" if survived >= k else "Only the spy and one civilian are left. "
        events.append(_outcome(SPY, f"{why}The spy was {the_spy.name} and the location was {loc}. The spy wins."))
        return Outcome(events=events, deaths=deaths)
    first = state.rng(f"first:{survived + 1}").choice(alive)
    events.append(NewEvent(kind="first", target=first.id, text=f"Round {survived + 1}. {first.name} asks first."))
    return Outcome(events=events, deaths=deaths)


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
        return "vote" if len(round_asks(state)) >= exchange_cap(state) else "ask"
    if state.events[-1].kind == "first":
        return "ask"  # the spy survived the vote: a new round
    if state.phase == "vote" and opt(state, "tie_revote") and state.events[-1].target is None:
        return "revote"  # the vote tied and nothing was decided
    return "last_chance"  # after a vote that accused the spy; every other ending is decided


def intent(state: GameState, p: Player) -> dict | None:
    """A seeded private plan for this turn. The spy blends in, or gets a window to name the location
    (likelier as the round goes on, and always on their last ask); a civilian probes or stays vague. With
    `ask_angle`, every ask turn also gets a topic to ask about, from its own seeded draw."""
    up = (state.phase == "ask" and p.id == asker(state)) or (state.phase == "answer" and p.id == answerer(state))
    if not up or state.winner:
        return None
    o = SPY_MODE.options | state.options
    done, now = asks(state), round_asks(state)
    rng = random.Random(f"{state.seed}:intent:{p.id}:{state.phase}:{len(done)}")
    angle = (
        {"angle": random.Random(f"{state.seed}:angle:{p.id}:{len(done)}").choice(ANGLES)}
        if o.get("ask_angle") and state.phase == "ask"
        else {}
    )
    return _plan(state, p, rng, done, now) | angle


def spy_window(state: GameState) -> bool:
    """Whether the spy, when someone else is about to ask, gets a seeded window to name the location first: only
    after an answer (new information), likelier as the round goes on. The spy's own ask turns use intent."""
    the_spy = spy(state)
    if state.winner or state.phase != "ask" or not the_spy.alive or asker(state) == the_spy.id:
        return False
    if next(e.kind for e in reversed(state.events) if e.kind != "phase") != "answer":
        return False
    o = SPY_MODE.options | state.options
    now = round_asks(state)
    chance = o["spy_guess_base"] + o["spy_guess_slope"] * len(now) / exchange_cap(state)
    return random.Random(f"{state.seed}:window:{len(asks(state))}").random() < chance


def _plan(state: GameState, p: Player, rng: random.Random, done: list, now: list) -> dict:
    o = SPY_MODE.options | state.options
    if p.role == SPY:
        if state.phase == "ask":
            mine = sum(e.actor == p.id for e in now)
            last = mine >= asks_per_player(state) - 1 or len(now) >= exchange_cap(state) - 1
            chance = o["spy_guess_base"] + o["spy_guess_slope"] * len(now) / exchange_cap(state)
            if last or rng.random() < chance:
                return {"plan": "guess_window"}
        return {"plan": "blend"}
    return {"plan": "probe" if rng.random() < o["civilian_probe"] else "vague"}


SPY_MODE = ModeConfig(
    name="spy_location",
    title=TITLE,
    rules="",  # set from the options below by configure()
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
        "revote": PhaseSpec(name="revote", type=PhaseType.SIMULTANEOUS),
        "last_chance": PhaseSpec(name="last_chance", type=PhaseType.SIMULTANEOUS),
    },
    first_phase="deal",
    new_day_phase="deal",
    transitions={"deal": "ask", "ask": "answer", "answer": "ask", "vote": "last_chance"},  # see next_phase
    next_phase=next_phase,
    options={
        "last_chance_guess": True,  # a spy caught by the vote may still name the location
        "last_chance_shortlist": False,  # ...from a short list (true location plus decoys), not all of them
        "asks_per_player": 1,  # each round's vote comes after this many questions from each player still in
        "spy_survive_votes": 2,  # the spy wins after surviving this many votes (1: the single-vote game)
        "giveaway_check": False,  # a civilian line using a giveaway word for the place or its cluster is retried once
        "tie_revote": True,  # a vote tie gets one revote between the tied players; a second tie: the spy wins
        "last_chance_result": "draw",  # "draw": a caught spy who names the place right draws; or "spy_wins"
        "shortlist_size": 5,
        "spy_guess_base": 0.05,  # the spy's chance of a guess window per turn, plus slope x progress (spy_window)
        "spy_guess_slope": 0.35,
        "civilian_probe": 0.6,  # a civilian's chance to probe rather than stay vague, per turn
        "roles": False,  # each civilian gets a secret role at the location (spy_roles.py); the spy gets none
        "min_generic_roles_per_game": 2,  # roles on: at least this many civilians get a generic role
        "ask_angle": False,  # each ask turn gets a seeded angle (what they wear, tools, who, a problem)
    },
    legal_actions=legal_actions,
    resolvers={
        "deal": resolve_deal,
        "ask": resolve_ask,
        "answer": resolve_answer,
        "vote": resolve_vote,
        "revote": resolve_vote,
        "last_chance": resolve_last_chance,
    },
    default_action=default_action,
    win_check=win_check,
    end_text=lambda state, winner, roles: (
        {DRAW: f"It's a draw. The location was {location(state)}.", SPY: "The spy wins!"}.get(
            winner, "The civilians win!"
        )
        + f" {roles}."
    ),
    intent=intent,
    interrupts=interrupt_actions,
    rules_for=lambda state: rules_text(SPY_MODE.options | state.options),
)


def configure(**options) -> None:
    """Set this mode's switches and the rules text that describes them (process-wide, like Mafia's)."""
    SPY_MODE.options.update(options)
    SPY_MODE.rules = rules_text(SPY_MODE.options)


configure()
