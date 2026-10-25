from engine.engine import MODES, new_game
from engine.models import ABSTAIN
from engine.modes.mafia import resolve_night, resolve_vote, win_check

MODE = MODES["mafia"]


def game(n=7, seed=1):
    return new_game(MODE, [f"P{i}" for i in range(n)], None, seed)


def by_role(state, role):
    return [p.id for p in state.players if p.role == role]


def test_doctor_save_cancels_kill():
    s = game()
    victim = by_role(s, "villager")[0]
    actions = {m: victim for m in by_role(s, "mafia")} | {by_role(s, "doctor")[0]: victim}
    out = resolve_night(s, actions)
    assert out.deaths == []


def test_unsaved_kill_happens_and_detective_learns():
    s = game()
    victim = by_role(s, "villager")[0]
    mafia = by_role(s, "mafia")
    det = by_role(s, "detective")[0]
    out = resolve_night(s, {m: victim for m in mafia} | {det: mafia[0]})
    assert out.deaths == [victim]
    assert any(e.vis == f"private:{det}" and "MAFIA" in e.text for e in out.events)


def test_vote_tie_eliminates_nobody():
    s = game(n=5)
    ids = [p.id for p in s.players]
    out = resolve_vote(s, {ids[0]: ids[1], ids[1]: ids[0], ids[2]: ABSTAIN, ids[3]: ABSTAIN, ids[4]: ABSTAIN})
    assert out.deaths == []


def test_vote_plurality_eliminates():
    s = game(n=5)
    ids = [p.id for p in s.players]
    out = resolve_vote(s, {ids[0]: ids[1], ids[2]: ids[1], ids[3]: ids[0], ids[1]: ABSTAIN, ids[4]: ids[1]})
    assert out.deaths == [ids[1]]


def test_resolvers_are_deterministic():
    s = game()
    a = {m: by_role(s, "villager")[i] for i, m in enumerate(by_role(s, "mafia"))}
    assert resolve_night(s, a) == resolve_night(s, a)


def test_win_conditions():
    s = game()
    for p in s.players:
        if p.role == "mafia":
            p.alive = False
    assert win_check(s) == "village"
    s = game()
    villagers = [p for p in s.players if p.role != "mafia"]
    for p in villagers[:-2]:
        p.alive = False
    assert win_check(s) == "mafia"


def test_mafia_can_never_target_a_teammate():
    import random

    from engine.engine import pending, submit_action, submit_say

    for seed in range(200):
        s = game(n=5 + seed % 5, seed=seed)
        rng = random.Random(seed)
        while not s.winner:
            reqs = pending(s)
            r = reqs[0]
            if r.kind == "speak":
                submit_say(s, r.pid, "hm")
                continue
            if s.phase == "night" and s.player(r.pid).role == "mafia":
                assert all(s.player(t).role != "mafia" for t in r.legal)
            submit_action(s, r.pid, rng.choice(r.legal))
