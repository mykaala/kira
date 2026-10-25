from collections import Counter

import pytest
from spy_bots import NAMES, play_spy

from engine.engine import IllegalMove, new_game, pending, submit_action
from engine.modes.spy_location import (
    ANSWER,
    CIVILIAN,
    CIVILIANS,
    GUESS,
    LOCATION_NAMES,
    SPY,
    SPY_MODE,
    asker,
    location,
    names_location,
    spy,
)


@pytest.fixture(autouse=True)
def default_options():
    before = dict(SPY_MODE.options)
    yield
    SPY_MODE.options.clear()
    SPY_MODE.options.update(before)


def game(n=6, seed=1):
    return new_game(SPY_MODE, NAMES[:n], None, seed)


def spy_to_ask(state):
    """Play one exchange if needed so the spy is the asker."""
    s = spy(state).id
    if asker(state) != s:
        submit_action(state, asker(state), s, text="what do you wear here?")
        submit_action(state, s, ANSWER, text="comfy stuff")
    assert asker(state) == s and state.phase == "ask"
    return s


def vote_for(state, target_of):
    for r in pending(state):
        submit_action(state, r.pid, target_of(r.pid))


def to_vote(state):
    while state.phase in ("ask", "answer"):
        r = pending(state)[0]
        plain = [a for a in r.legal if not a.startswith(GUESS)]
        submit_action(state, r.pid, plain[0], text="x")
    assert state.phase == "vote"


def test_deal_gives_one_spy_and_a_location():
    s = game()
    assert Counter(p.role for p in s.players) == {CIVILIAN: 5, SPY: 1}
    assert location(s) in LOCATION_NAMES and s.phase == "ask"


def test_right_guess_wins_for_the_spy_and_wrong_loses():
    s = game()
    sp = spy_to_ask(s)
    submit_action(s, sp, GUESS + location(s))
    assert s.winner == SPY
    s = game()
    sp = spy_to_ask(s)
    submit_action(s, sp, GUESS + next(x for x in LOCATION_NAMES if x != location(s)))
    assert s.winner == CIVILIANS


def test_civilians_cannot_guess():
    s = next(s for seed in range(20) if (s := game(seed=seed)).player(asker(s)).role == CIVILIAN)
    assert not any(a.startswith(GUESS) for a in pending(s)[0].legal)
    with pytest.raises(IllegalMove):
        submit_action(s, asker(s), GUESS + location(s))


def test_vote_on_spy_with_last_chance():
    for right, winner in ((True, SPY), (False, CIVILIANS)):
        s = game()
        to_vote(s)
        sp = spy(s).id
        vote_for(s, lambda pid: sp if pid != sp else next(p.id for p in s.players if p.id != sp))
        assert s.phase == "last_chance" and not s.winner
        assert [r.pid for r in pending(s)] == [sp]
        guess = location(s) if right else next(x for x in LOCATION_NAMES if x != location(s))
        submit_action(s, sp, GUESS + guess)
        assert s.winner == winner


def test_vote_on_spy_without_last_chance_ends_it():
    SPY_MODE.options["last_chance_guess"] = False
    s = game()
    to_vote(s)
    sp = spy(s).id
    vote_for(s, lambda pid: sp if pid != sp else next(p.id for p in s.players if p.id != sp))
    assert s.winner == CIVILIANS


def test_wrong_vote_and_tie_mean_the_spy_wins():
    s = game()
    to_vote(s)
    sp = spy(s).id
    civ = next(p.id for p in s.players if p.id != sp)
    vote_for(s, lambda pid: civ if pid != civ else sp)
    assert s.winner == SPY
    s = game()
    to_vote(s)
    ids = [p.id for p in s.players]
    a, b = ids[0], ids[1]  # 6 players: 3 votes each
    vote_for(s, lambda pid: {a: b, b: a}.get(pid, a if ids.index(pid) % 2 else b))
    assert s.winner == SPY and any(e.kind == "accused" and e.target is None for e in s.events)


def test_shortlist_limits_the_last_chance():
    SPY_MODE.options["last_chance_shortlist"] = True
    s = game()
    to_vote(s)
    sp = spy(s).id
    vote_for(s, lambda pid: sp if pid != sp else next(p.id for p in s.players if p.id != sp))
    legal = pending(s)[0].legal
    assert len(legal) == 5 and GUESS + location(s) in legal


def test_exchanges_respect_the_cap_and_the_ask_back_rule():
    for seed in range(300):
        n = 5 + seed % 4
        s = play_spy(seed, n=n, guess_rate=0)
        asks = [e for e in s.events if e.kind == "ask"]
        assert len(asks) <= 2 * n
        assert max(Counter(e.actor for e in asks).values()) <= 2
        for prev, cur in zip(asks, asks[1:]):
            assert cur.actor == prev.target  # the target asks next
            if cur.target == prev.actor:  # asking back only when nobody else was left
                others = [p.id for p in s.players if p.id not in (cur.actor, prev.actor)]
                done = Counter(e.actor for e in asks[: asks.index(cur)])
                assert all(done[o] >= 2 for o in others) or asks.index(cur) == 2 * n - 1


def test_texts_are_posted_and_stock_lines_fill_gaps():
    s = game()
    a = asker(s)
    target = pending(s)[0].legal[0]
    submit_action(s, a, target, text="how loud is it?")
    submit_action(s, target, ANSWER)
    ask, answer = [e for e in s.events if e.kind in ("ask", "answer")]
    assert ask.text == "how loud is it?" and answer.text  # stock answer


def test_random_games_finish_and_are_deterministic():
    for seed in range(500):
        s = play_spy(seed, n=5 + seed % 4)
        assert s.winner in (SPY, CIVILIANS)
    a, b = play_spy(42, n=7), play_spy(42, n=7)
    assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]


def test_names_location():
    assert names_location("we're on the Ferry lol", "ferry")
    assert names_location("ugh the dentist again", "dentist office")
    assert names_location("hot-springs vibes", "hot spring")
    assert not names_location("the smell of salt", "ferry")
    assert not names_location("trainers on", "sleeper train")
