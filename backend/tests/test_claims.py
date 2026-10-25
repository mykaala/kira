import json
from collections import Counter

import pytest

from bots import play_random
from engine.engine import MODES, IllegalMove, new_game, pending, submit_action, submit_say
from engine.models import ClaimIn
from engine.views import build_view

MODE = MODES["mafia"]
NAMES = ["Ana", "Bo", "Cy", "Dee", "Eli", "Fay", "Gus"]


def to_day_one_discussion(seed=1):
    """A 7-player game played through night 1 with the detective checking the first mafia."""
    state = new_game(MODE, NAMES, None, seed)
    mafia = [p.id for p in state.players if p.role == "mafia"]
    for r in pending(state):
        role = state.player(r.pid).role
        submit_action(state, r.pid, mafia[0] if role == "detective" else "abstain")
    assert state.phase == "discussion"
    return state, mafia


def by_role(state, role):
    return next(p.id for p in state.players if p.role == role)


def speak_as(state, pid, text="hi", claim=None):
    state.queue.insert(0, pid)  # put them up next
    submit_say(state, pid, text, claim)


def test_real_detective_can_claim_only_real_results():
    state, mafia = to_day_one_discussion()
    det = by_role(state, "detective")
    villager = by_role(state, "villager")
    with pytest.raises(IllegalMove, match="came back mafia"):
        speak_as(state, det, claim=ClaimIn(role="detective", target=mafia[0], result="not mafia"))
    with pytest.raises(IllegalMove, match="never checked"):
        speak_as(state, det, claim=ClaimIn(role="detective", target=villager, result="mafia"))
    speak_as(state, det, claim=ClaimIn(role="detective", target=mafia[0], result="mafia"))
    assert state.claims[-1].true and state.claims[-1].seq == state.events[-1].seq


def test_mafia_can_claim_anything_and_it_is_logged_false():
    state, mafia = to_day_one_discussion()
    det = by_role(state, "detective")
    speak_as(state, mafia[1], claim=ClaimIn(role="detective", target=det, result="mafia"))
    c = state.claims[-1]
    assert c.actor == mafia[1] and not c.true
    # everyone sees the claim, nobody sees whether it is true
    view = build_view(MODE, state, det)
    assert view.claims[-1].actor == mafia[1] and "true" not in json.dumps(view.model_dump()["claims"])


def test_repeating_a_claim_logs_it_once():
    state, mafia = to_day_one_discussion()
    det = by_role(state, "detective")
    claim = ClaimIn(role="detective", target=det, result="mafia")
    speak_as(state, mafia[1], claim=claim)
    speak_as(state, mafia[1], "still saying it", claim=claim)
    assert len(state.claims) == 1


def test_bad_claims_are_rejected():
    state, _ = to_day_one_discussion()
    pid = by_role(state, "villager")
    for claim in [
        ClaimIn(role="mafia"),
        ClaimIn(role="doctor", target=pid),
        ClaimIn(role="doctor", target=by_role(state, "doctor"), result="mafia"),
    ]:
        with pytest.raises(IllegalMove):
            speak_as(state, pid, claim=claim)
    speak_as(state, pid, claim=ClaimIn(role="doctor"))
    assert not state.claims[-1].true


def test_intent_is_seeded_and_only_for_mafia_and_detective():
    a, _ = to_day_one_discussion(seed=5)
    b, _ = to_day_one_discussion(seed=5)
    for p in a.players:
        ia, ib = build_view(MODE, a, p.id).intent, build_view(MODE, b, p.id).intent
        assert ia == ib
        assert (ia is not None) == (p.role in ("mafia", "detective"))  # this detective checked a mafia


def test_fake_claim_targets_a_living_hidden_player_and_counterclaims_follow_claims():
    talks = Counter()
    for seed in range(400):
        state, mafia = to_day_one_discussion(seed)
        plans = {m: build_view(MODE, state, m).intent for m in mafia}
        claimers = [m for m, p in plans.items() if p["talk"] == "fake_claim"]
        assert len(claimers) <= 1  # one bluffer per team per day
        for m in claimers:
            t = plans[m]["claim"]["target"]
            assert t != m and state.player(t).alive
            assert (state.player(t).role == "mafia") == (plans[m]["claim"]["result"] == "not mafia")
        talks["fake" if claimers else "blend"] += 1
        # once someone else claims detective, the same roll can turn into a counterclaim
        det = by_role(state, "detective")
        speak_as(state, det, claim=ClaimIn(role="detective", target=mafia[0], result="mafia"))
        after = [build_view(MODE, state, m).intent for m in mafia]
        counter = [p for p in after if p["talk"] == "counterclaim"]
        assert all(p["claim"]["target"] == det for p in counter)
        talks["counter"] += bool(counter)
    assert 0.43 < talks["fake"] / 400 < 0.57  # fake_claim_p on day 1 is 0.5
    assert 0.18 < talks["counter"] / 400 < 0.32  # counterclaim_p is 0.25


def test_no_counterclaim_against_a_claim_that_clears_someone():
    for seed in range(200):
        state, mafia = to_day_one_discussion(seed)
        villager = by_role(state, "villager")
        speak_as(
            state, by_role(state, "villager"), claim=ClaimIn(role="detective", target=mafia[0], result="not mafia")
        )
        speak_as(state, by_role(state, "doctor"), claim=ClaimIn(role="detective", target=villager, result="mafia"))
        assert all(build_view(MODE, state, m).intent["talk"] != "counterclaim" for m in mafia)


def test_detective_with_a_hit_reveals_on_day_one_half_the_time_or_when_named():
    reveal = 0
    for seed in range(400):
        state, mafia = to_day_one_discussion(seed)
        det = by_role(state, "detective")
        plan = build_view(MODE, state, det).intent
        if plan["talk"] == "reveal":
            reveal += 1
            assert plan["claim"] == {"role": "detective", "target": mafia[0], "result": "mafia"}
        else:
            assert plan == {"talk": "hold"}
            speak_as(state, mafia[0], f"{state.player(det).name} is quiet")
            assert build_view(MODE, state, det).intent["talk"] == "reveal"
    assert 0.42 < reveal / 400 < 0.58  # detective_day1_claim_p is 0.5


def to_night_two(seed=1):
    state, mafia = to_day_one_discussion(seed)
    while state.phase != "night":
        for r in pending(state):
            if r.kind == "act":
                submit_action(state, r.pid, "abstain")
            else:
                submit_say(state, r.pid, "hm")
    return state, mafia


def test_night_kill_plan_prefers_a_claimed_detective_then_the_most_trusted():
    state, mafia = to_day_one_discussion()
    det = by_role(state, "detective")
    speak_as(state, det, claim=ClaimIn(role="detective", target=mafia[0], result="mafia"))
    while state.phase != "night":
        for r in pending(state):
            if r.kind == "act":
                submit_action(state, r.pid, "abstain")
            else:
                submit_say(state, r.pid, "hm")
    plan = build_view(MODE, state, mafia[0]).intent
    assert tuple(plan["kill"]) == (det, "claimed detective")
    # nobody else gets a night plan
    assert build_view(MODE, state, by_role(state, "villager")).intent is None


def test_night_kill_plan_without_claims_picks_fewest_votes():
    from engine.modes.mafia import kill_target

    state, mafia = to_night_two(seed=4)
    target, why = kill_target(state, mafia)
    assert state.player(target).role != "mafia" and "trusts most" in why


def test_detective_without_a_hit_gets_no_plan():
    state = new_game(MODE, NAMES, None, 2)
    for r in pending(state):
        submit_action(
            state, r.pid, by_role(state, "villager") if state.player(r.pid).role == "detective" else "abstain"
        )
    assert build_view(MODE, state, by_role(state, "detective")).intent is None


def test_vote_split_assigns_different_jobs():
    splits = 0
    for seed in range(300):
        state, mafia = to_day_one_discussion(seed)
        votes = [build_view(MODE, state, m).intent["vote"] for m in mafia]
        if votes[0] != "free":
            splits += 1
            assert sorted(votes) == ["follow", "own"]
    assert 0.52 < splits / 300 < 0.68  # split_vote_p is 0.6


def test_claims_survive_full_random_games():
    for seed in range(100):
        state = play_random(seed)
        assert state.winner
        for c in state.claims:
            assert state.events[c.seq].kind == "say" and state.events[c.seq].actor == c.actor
