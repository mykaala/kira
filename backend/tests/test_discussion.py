"""Every living player speaks in every day's discussion, and nobody speaks twice
before everyone has spoken once."""

from bots import play_random


def discussion_days(state):
    """(day, players alive when discussion opened, say events that day)"""
    for start in (e for e in state.events if e.kind == "phase" and e.phase == "discussion"):
        dead = {
            e.target for e in state.events if e.seq < start.seq and e.target and e.kind in {"morning", "elimination"}
        }
        alive = {p.id for p in state.players} - dead
        says = [e for e in state.events if e.kind == "say" and e.day == start.day]
        yield start.day, alive, says


def test_every_living_player_speaks_every_day():
    for seed in range(200):
        state = play_random(seed, n=5 + seed % 5)
        for day, alive, says in discussion_days(state):
            missing = alive - {e.actor for e in says}
            assert not missing, f"seed {seed} day {day}: {missing} never spoke"


def test_nobody_speaks_twice_before_everyone_once():
    for seed in range(200):
        state = play_random(seed, n=5 + seed % 5, human_index=None)
        for day, alive, says in discussion_days(state):
            first_round = [e.actor for e in says[: len(alive)]]
            assert len(set(first_round)) == len(alive), f"seed {seed} day {day}: {first_round}"
            assert len(says) <= len(alive) + 3


def test_human_interjection_uses_their_round_one_slot():
    for seed in range(200):
        state = play_random(seed, n=7)
        for day, alive, says in discussion_days(state):
            human_says = [e for e in says if e.actor == "p0"]
            scheduled = [e for e in says if e.actor != "p0"]
            ai_alive = alive - {"p0"}
            assert {e.actor for e in scheduled[: len(ai_alive)]} == ai_alive
            if "p0" in alive:
                assert human_says


def test_call_vote_ends_discussion_and_opens_the_vote():
    from engine.engine import MODES, call_vote, new_game, pending, submit_action, turns_left

    s = new_game(MODES["mafia"], [f"P{i}" for i in range(7)], 0, 5)
    while s.phase != "discussion":
        for r in pending(s):
            submit_action(s, r.pid, r.legal[0])
    left, total = turns_left(s)
    assert left == total == 7 + 3  # everyone once, then 3 extra AI speakers
    call_vote(s)
    assert s.phase == "vote" and turns_left(s) == (0, 0)


def test_turns_left_counts_down_as_people_speak():
    from engine.engine import MODES, new_game, pending, submit_action, submit_say, turns_left

    s = new_game(MODES["mafia"], [f"P{i}" for i in range(7)], None, 5)
    while s.phase != "discussion":
        for r in pending(s):
            submit_action(s, r.pid, r.legal[0])
    seen = []
    while s.phase == "discussion":
        seen.append(turns_left(s))
        submit_say(s, s.queue[0], "hm")
    assert [left for left, _ in seen] == list(range(len(seen), 0, -1))
    assert len({total for _, total in seen}) == 1
