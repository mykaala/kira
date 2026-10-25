from engine.engine import MODES, IllegalMove, new_game, pending, submit_action

import pytest

MODE = MODES["mafia"]


def night_requests(state):
    return {state.player(r.pid).role: r for r in pending(state)}


def play_to_next_night(state, protect):
    """Finish this night with the doctor protecting `protect`; the day passes with nobody voted out."""
    for r in pending(state):
        role = state.player(r.pid).role
        submit_action(state, r.pid, protect if role == "doctor" else "abstain" if "abstain" in r.legal else r.legal[0])
    while state.phase != "night" and not state.winner:
        for r in pending(state):
            if r.kind == "act":
                submit_action(state, r.pid, "abstain")
            else:
                from engine.engine import submit_say

                submit_say(state, r.pid, "hm")


def test_night_one_save_does_not_count_because_nobody_can_be_killed():
    state = new_game(MODE, [f"P{i}" for i in range(7)], None, 3)
    doctor = night_requests(state)["doctor"]
    play_to_next_night(state, doctor.pid)
    assert doctor.pid in night_requests(state)["doctor"].legal


def test_doctor_cannot_protect_the_same_player_two_nights_running():
    state = new_game(MODE, [f"P{i}" for i in range(7)], None, 3)
    doctor = night_requests(state)["doctor"]
    play_to_next_night(state, "abstain")
    target = doctor.pid
    play_to_next_night(state, target)
    assert state.day == 3 and state.player(target).alive
    legal = night_requests(state)["doctor"].legal
    assert target not in legal and "abstain" in legal
    with pytest.raises(IllegalMove):
        submit_action(state, doctor.pid, target)


def test_the_repeat_is_allowed_again_a_night_later():
    state = new_game(MODE, [f"P{i}" for i in range(7)], None, 3)
    doctor = night_requests(state)["doctor"]
    me = doctor.pid  # protecting yourself keeps you alive through the mafia's kills
    play_to_next_night(state, "abstain")
    play_to_next_night(state, me)
    other = next(t for t in night_requests(state)["doctor"].legal if t not in ("abstain", me))
    play_to_next_night(state, other)
    if state.winner or not state.player(me).alive:
        pytest.skip("game ended before night 3 with this seed")
    assert me in night_requests(state)["doctor"].legal
