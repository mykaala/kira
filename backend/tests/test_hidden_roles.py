"""Roles stay hidden on death (the default) and are shown only when the game ends; the
house rule can switch the reveal back on."""

import pytest

from agents.personas import CAST
from agents.prompt import observation, shared_block
from agents.schemas import BeliefState
from bots import play_random
from engine.engine import MODES
from engine.views import build_view

MODE = MODES["mafia"]


def _with_reveal(value):
    before = MODE.reveal_role_on_death
    MODE.reveal_role_on_death = value
    yield
    MODE.reveal_role_on_death = before


@pytest.fixture
def hidden():
    yield from _with_reveal(False)


@pytest.fixture
def revealed():
    yield from _with_reveal(True)


def test_hidden_is_the_default():
    from server.settings import Settings

    assert MODE.reveal_role_on_death is False and Settings(_env_file=None).reveal_role_on_death is False


def check(state):
    if state.winner:
        return
    for e in state.events:
        if e.kind in ("morning", "elimination"):
            assert "They were" not in e.text, e.text
    for viewer in state.players:
        view = build_view(MODE, state, viewer.id)
        assert not view.roles_revealed_on_death and "NOT revealed" in view.rules
        for info in view.players:
            other = state.player(info.id)
            if info.role and info.id != viewer.id:
                assert viewer.role == "mafia" and other.role == "mafia", f"{viewer.name} sees {other.name}"
        if any(not p.alive for p in state.players):
            obs = observation(view, CAST[0], BeliefState(), "discussion", ["none"])
            assert "(role unknown)" in obs or all(p.alive or p.role for p in view.players)


def test_dead_roles_stay_hidden_until_the_end(hidden):
    for seed in range(100):
        state = play_random(seed, on_step=check)
        end = build_view(MODE, state, state.players[0].id)
        assert all(p.role for p in end.players)  # all shown once the game is over
        assert next(e for e in state.events if e.kind == "game_over").text.count(" was ") == len(state.players)


def test_prompt_never_says_roles_are_revealed(hidden):
    view = build_view(MODE, play_random(1), "p0")
    block = shared_block(view.rules, view.roles_revealed_on_death)
    assert "role is revealed" not in block and "Use every flip" not in block and "NOT revealed" in block


def test_reveal_house_rule_still_works(revealed):
    state = play_random(2)
    deaths = [e for e in state.events if e.kind in ("morning", "elimination") and e.target]
    assert deaths and all("They were" in e.text for e in deaths)
