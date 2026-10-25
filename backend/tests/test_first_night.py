from bots import play_random
from engine.engine import MODES, new_game, pending


def test_nobody_dies_on_night_one():
    for seed in range(200):
        state = play_random(seed, n=5 + seed % 5)
        morning = next(e for e in state.events if e.kind == "morning" and e.day == 1)
        assert morning.text == "Day 1 begins. No one has died yet.", f"seed {seed}: {morning.text}"
        assert not any(e.kind == "mafia_choice" and e.day == 1 for e in state.events)


def test_detective_and_doctor_still_act_on_night_one():
    state = new_game(MODES["mafia"], [f"P{i}" for i in range(7)], None, 3)
    acting = {state.player(r.pid).role for r in pending(state)}
    assert acting == {"detective", "doctor"}


def test_morning_line_is_the_first_public_line_of_each_day():
    for seed in range(50):
        state = play_random(seed)
        for e in state.events:
            if e.kind == "phase" and e.phase == "morning":
                nxt = state.events[e.seq + 1]
                assert nxt.kind == "morning" and nxt.vis == "public"


def test_win_checked_after_every_phase():
    # a game always ends the moment a side wins: no phase opens after a win
    for seed in range(200):
        state = play_random(seed, n=5 + seed % 5)
        assert state.events[-1].kind == "game_over"
        assert sum(e.kind == "game_over" for e in state.events) == 1
