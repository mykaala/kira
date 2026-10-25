import pytest

from bots import play_random
from engine.engine import MODES, new_game
from engine.models import ABSTAIN
from engine.modes.mafia import resolve_night, resolve_vote, win_check
from engine.views import build_view
from test_leak import check_views

MODE = MODES["mafia"]
BOTH = ("jester", "bodyguard")


def game(n=8, seed=1, extras=BOTH):
    return new_game(MODE, [f"P{i}" for i in range(n)], None, seed, extras)


def by_role(s, role):
    return [p.id for p in s.players if p.role == role]


def test_optional_roles_replace_villagers():
    s = game()
    roles = sorted(p.role for p in s.players)
    assert roles.count("jester") == 1 and roles.count("bodyguard") == 1
    assert roles.count("villager") == len(s.players) - 2 - 2 - 2  # 2 mafia, detective, doctor, 2 extras


def test_too_few_villagers_is_refused():
    with pytest.raises(ValueError):
        new_game(MODE, [f"P{i}" for i in range(5)], None, 1, BOTH + ("jester",))


def test_bodyguard_dies_in_place_of_the_guarded_player():
    s = game()
    target = by_role(s, "villager")[0]
    guard = by_role(s, "bodyguard")[0]
    actions = {m: target for m in by_role(s, "mafia")} | {guard: target}
    assert resolve_night(s, actions).deaths == [guard]


def test_doctor_save_beats_the_bodyguard():
    s = game()
    target = by_role(s, "villager")[0]
    actions = (
        {m: target for m in by_role(s, "mafia")}
        | {by_role(s, "bodyguard")[0]: target}
        | {by_role(s, "doctor")[0]: target}
    )
    assert resolve_night(s, actions).deaths == []


def test_jester_voted_out_wins_alone():
    s = game()
    jester = by_role(s, "jester")[0]
    votes = {p.id: jester for p in s.players if p.id != jester} | {jester: ABSTAIN}
    out = resolve_vote(s, votes)
    s.player(jester).alive = False
    from engine.engine import _emit

    for e in out.events:
        _emit(s, e)
    assert win_check(s) == "jester"


def test_jester_is_not_mafia_to_the_detective_and_has_no_night_action():
    s = game()
    jester = by_role(s, "jester")[0]
    det = by_role(s, "detective")[0]
    out = resolve_night(s, {det: jester})
    assert any("not mafia" in e.text for e in out.events)
    assert build_view(MODE, s, jester).legal_actions == []  # night 1, no action
    assert build_view(MODE, s, jester).team == "jester"


def test_random_games_with_both_roles_finish_without_leaks():
    winners = set()
    for seed in range(300):
        state = play_random(seed, n=7 + seed % 3, extra_roles=BOTH, on_step=check_views)
        assert state.winner in {"village", "mafia", "jester"}
        winners.add(state.winner)
    assert winners == {"village", "mafia", "jester"}
