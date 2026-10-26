from collections import Counter

import pytest
from spy_bots import NAMES, play_spy

from engine.engine import IllegalMove, interrupt, new_game, pending, submit_action
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
    round_no,
    spy,
    votes_survived,
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


def test_the_spy_can_name_the_place_on_anyone_s_turn():
    wrong = lambda s: next(x for x in LOCATION_NAMES if x != location(s))  # noqa: E731
    for phase in ("ask", "answer"):
        for right, winner in ((True, SPY), (False, CIVILIANS)):
            s = next(s for seed in range(20) if (s := game(seed=seed)).player(asker(s)).role == CIVILIAN)
            if phase == "answer":
                civilian = next(a for a in pending(s)[0].legal if a != spy(s).id)
                submit_action(s, asker(s), civilian, text="what do you wear here?")
            assert s.phase == phase and spy(s).id not in {r.pid for r in pending(s)}  # someone else is up
            interrupt(s, spy(s).id, GUESS + (location(s) if right else wrong(s)))
            assert s.winner == winner
            assert [e.actor for e in s.events if e.kind == "guess"] == [spy(s).id]


def test_only_the_spy_guesses_out_of_turn_and_only_during_the_questions():
    s = game()
    civilian = next(p.id for p in s.players if p.role == CIVILIAN)
    with pytest.raises(IllegalMove):
        interrupt(s, civilian, GUESS + location(s))
    to_vote(s)
    with pytest.raises(IllegalMove):
        interrupt(s, spy(s).id, GUESS + location(s))
    assert not s.winner


def test_vote_on_spy_with_last_chance():
    SPY_MODE.options["last_chance_result"] = "spy_wins"
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


def test_wrong_vote_and_tie_mean_the_spy_wins_in_the_single_vote_game():
    SPY_MODE.options["tie_revote"] = False
    SPY_MODE.options["spy_survive_votes"] = 1
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
    assert len(legal) == 6 and GUESS + location(s) in legal and legal[-1] == GUESS + "-"


def rounds(s):
    """The game split into voting rounds: (players still in, the round's asks, the round's votes)."""
    starts = [i for i, e in enumerate(s.events) if e.kind == "first"] + [len(s.events)]
    out = []
    for a, b in zip(starts, starts[1:]):
        evs = s.events[a:b]
        gone = {e.target for e in s.events[:a] if e.kind == "accused" and e.target}  # voted out in earlier rounds
        alive = [p.id for p in s.players if p.id not in gone]
        out.append((alive, [e for e in evs if e.kind == "ask"], [e for e in evs if e.kind == "vote"]))
    return out


def test_rounds_run_to_the_end_and_each_vote_comes_only_after_its_last_question():
    """No early votes: with no guess, every voting round asks exactly asks_per_player x (players still in)
    questions, everyone still in asks once per pass, the target asks next, and asking back happens only when
    nobody else is left. Only players still in ask, answer or vote."""
    for k in (1, 2, 3):
        SPY_MODE.options["spy_survive_votes"] = k
        for per in (1, 2):
            SPY_MODE.options["asks_per_player"] = per
            for seed in range(100):
                s = play_spy(seed, n=5 + seed % 4, guess_rate=0)
                assert not any(e.kind == "info" for e in s.events)  # "nobody left to ask" never happens
                assert len(rounds(s)) == round_no(s) <= k
                for alive, asks, votes in rounds(s):
                    n = len(alive)
                    assert len(asks) == per * n, (k, per, seed, len(asks))
                    for r in range(per):
                        assert sorted(e.actor for e in asks[r * n : (r + 1) * n]) == sorted(alive)
                    assert {e.target for e in asks} <= set(alive) and {v.actor for v in votes} <= set(alive)
                    assert {v.target for v in votes} <= set(alive)
                    assert votes and min(v.seq for v in votes) > asks[-1].seq
                    for i, (prev, cur) in enumerate(zip(asks, asks[1:])):
                        assert cur.actor == prev.target  # the target asks next
                        if cur.target == prev.actor:  # asking back only when nobody else was left
                            done = Counter(e.actor for e in asks[: i + 1])
                            rnd = (i + 1) // n + 1
                            others = [o for o in alive if o not in (cur.actor, prev.actor)]
                            assert all(done[o] >= rnd for o in others)


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
        assert s.winner in (SPY, CIVILIANS, "draw")
    a, b = play_spy(42, n=7), play_spy(42, n=7)
    assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]


def test_names_location():
    assert names_location("we're on the Ferry lol", "ferry")
    assert names_location("ugh the dentist again", "dentist office")
    assert names_location("hot-springs vibes", "hot spring")
    assert not names_location("the smell of salt", "ferry")
    assert not names_location("my car is a mess", "cable car")
    assert names_location("the vet's waiting room", "vet clinic")


def test_one_question_each_then_the_forced_vote():
    from engine.modes.spy_location import rules_text

    SPY_MODE.options["asks_per_player"] = 1
    for seed in range(200):
        n = 5 + seed % 4
        s = play_spy(seed, n=n, guess_rate=0)
        for _, asks, votes in rounds(s):
            assert len(asks) <= n and max(Counter(e.actor for e in asks).values()) == 1
            assert votes
    assert "asks about one question;" in rules_text(SPY_MODE.options)


def tie_vote(s, a_votes_for=None):
    """Everyone votes so that p0 and p1 tie at 3 each (6 players)."""
    ids = [p.id for p in s.players]
    a, b = ids[0], ids[1]
    vote_for(s, lambda pid: {a: b, b: a}.get(pid, a if ids.index(pid) % 2 else b))
    return a, b


def test_tie_revote_between_the_tied_players_only():
    from engine.modes.spy_location import rules_text

    SPY_MODE.options["tie_revote"] = True
    assert "votes once more between the tied players only" in rules_text(SPY_MODE.options)
    s = game()
    to_vote(s)
    a, b = tie_vote(s)
    assert s.phase == "revote" and not s.winner
    legal = {r.pid: r.legal for r in pending(s)}
    assert legal[a] == [b] and legal[b] == [a] and all(set(v) == {a, b} for k, v in legal.items() if k not in (a, b))
    # a second tie: nobody is out and the spy has survived the vote; with one vote to survive, the spy wins
    SPY_MODE.options["spy_survive_votes"] = 1
    ids = [p.id for p in s.players]
    vote_for(s, lambda pid: {a: b, b: a}.get(pid, a if ids.index(pid) % 2 else b))
    assert s.winner == SPY and "tied again" in [e for e in s.events if e.kind == "accused"][-1].text
    assert all(p.alive for p in s.players)


def test_revote_that_finds_the_spy_goes_to_the_last_chance():
    SPY_MODE.options["tie_revote"] = True
    for seed in range(40):
        s = game(seed=seed)
        to_vote(s)
        a, b = tie_vote(s)
        sp = spy(s).id
        if sp in (a, b):
            other = b if sp == a else a
            vote_for(s, lambda pid: sp if pid != sp else other)
            assert s.phase == "last_chance"
            return
    raise AssertionError("no seed put the spy in the tie")


def test_vote_tie_without_revote_still_ends_it():
    SPY_MODE.options["tie_revote"] = False
    SPY_MODE.options["spy_survive_votes"] = 1
    s = game()
    to_vote(s)
    tie_vote(s)
    assert s.winner == SPY and s.phase == "vote"


def test_draw_on_a_right_last_chance_only():
    from engine.modes.spy_location import DRAW, rules_text

    SPY_MODE.options["last_chance_result"] = "draw"
    assert "right and the game is a draw" in rules_text(SPY_MODE.options)
    for right, winner in ((True, DRAW), (False, CIVILIANS)):
        s = game()
        to_vote(s)
        sp = spy(s).id
        vote_for(s, lambda pid: sp if pid != sp else next(p.id for p in s.players if p.id != sp))
        guess = location(s) if right else next(x for x in LOCATION_NAMES if x != location(s))
        submit_action(s, sp, GUESS + guess)
        assert s.winner == winner
        end = s.events[-1].text
        assert end.startswith("It's a draw. The location was") if right else end.startswith("The civilians win!")
    # a right guess on the spy's own turn still wins outright
    s = game()
    sp = spy_to_ask(s)
    submit_action(s, sp, GUESS + location(s))
    assert s.winner == SPY


def test_rules_spell_out_the_question_count():
    from engine.modes.spy_location import rules_text

    assert "asks about two questions;" in rules_text(SPY_MODE.options | {"asks_per_player": 2})
    assert "asks about one question;" in rules_text(SPY_MODE.options | {"asks_per_player": 1})


# --- surviving K votes ---------------------------------------------------------------------------


def vote_out(s, out):
    """Everyone still in votes `out` out (`out` votes for someone else)."""
    other = next(p.id for p in s.alive() if p.id != out)
    vote_for(s, lambda pid: out if pid != out else other)


def test_a_civilian_voted_out_leaves_and_a_new_round_starts():
    SPY_MODE.options["spy_survive_votes"] = 2
    s = game()
    to_vote(s)
    sp = spy(s).id
    civ = next(p.id for p in s.players if p.id != sp)
    vote_out(s, civ)
    assert not s.winner and s.phase == "ask" and not s.player(civ).alive
    accused = [e for e in s.events if e.kind == "accused"][-1]
    assert accused.target == civ and accused.text.endswith("is voted out, and was a civilian.")
    assert votes_survived(s) == 1 and round_no(s) == 2
    assert "survived 1 of 2 votes" in [e for e in s.events if e.kind == "survived"][-1].text
    first = s.events[-2] if s.events[-1].kind == "phase" else s.events[-1]
    assert first.kind == "first" and first.text.startswith("Round 2.") and first.target != civ
    # the player who is out never asks, answers, is asked, or votes
    while s.phase in ("ask", "answer"):
        (r,) = pending(s)
        assert r.pid != civ and civ not in r.legal
        submit_action(s, r.pid, [a for a in r.legal if not a.startswith(GUESS)][0], text="x")
    assert s.phase == "vote" and len([e for e in s.events if e.kind == "ask" and e.seq > first.seq]) == 5
    assert all(r.pid != civ and civ not in r.legal for r in pending(s))
    civ2 = next(p.id for p in s.alive() if p.id != sp)
    vote_out(s, civ2)
    assert s.winner == SPY and votes_survived(s) == 2


def test_a_second_tie_counts_as_a_survived_vote():
    SPY_MODE.options["spy_survive_votes"] = 2
    s = game()
    to_vote(s)
    a, b = tie_vote(s)
    ids = [p.id for p in s.players]
    vote_for(s, lambda pid: {a: b, b: a}.get(pid, a if ids.index(pid) % 2 else b))
    assert not s.winner and s.phase == "ask" and all(p.alive for p in s.players)
    assert votes_survived(s) == 1 and round_no(s) == 2


def test_the_spy_wins_when_only_one_civilian_is_left():
    SPY_MODE.options["spy_survive_votes"] = 9
    s = game(n=5)
    sp = spy(s).id
    for out in range(3):
        to_vote(s)
        vote_out(s, next(p.id for p in s.alive() if p.id != sp))
    assert s.winner == SPY and len(s.alive()) == 2
    assert "Only the spy and one civilian are left." in [e for e in s.events if e.kind == "outcome"][-1].text


def test_in_a_later_round_the_spy_can_still_name_the_place_or_be_caught():
    SPY_MODE.options["spy_survive_votes"] = 3
    for right in (True, False):
        s = game()
        to_vote(s)
        sp = spy(s).id
        vote_out(s, next(p.id for p in s.alive() if p.id != sp))
        spy_to_ask(s)
        guess = location(s) if right else next(x for x in LOCATION_NAMES if x != location(s))
        submit_action(s, sp, GUESS + guess)
        assert s.winner == (SPY if right else CIVILIANS)
    s = game()
    to_vote(s)
    sp = spy(s).id
    vote_out(s, next(p.id for p in s.alive() if p.id != sp))
    to_vote(s)
    vote_out(s, sp)
    assert s.phase == "last_chance" and pending(s)[0].pid == sp


def test_one_vote_rules_text_is_unchanged_and_more_votes_explain_rounds():
    from engine.modes.spy_location import rules_text

    one = rules_text(SPY_MODE.options | {"spy_survive_votes": 1})
    assert one.endswith("If the vote accuses a civilian, or ties, the spy wins.") and "round" not in one.lower()
    two = rules_text(SPY_MODE.options | {"spy_survive_votes": 2})
    assert "surviving two votes" in two and "only the spy and one civilian are left" in two
    assert "they were a civilian" in two
