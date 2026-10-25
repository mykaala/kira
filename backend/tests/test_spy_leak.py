"""The spy's view never contains the location (until the game is over), and no view shows another
player's role. The location reaches civilians only, on their channel."""

import json

import pytest
from spy_bots import play_spy

from agents.personas import CAST
from agents.spy_prompt import observation
from engine.models import PUBLIC, channel, private
from engine.modes.spy_location import CIVILIANS, GUESS, LOCATION_NAMES, SPY, SPY_MODE, location
from engine.views import build_view

MODE = SPY_MODE


def check_views(state):
    if state.winner:
        return
    loc = location(state)
    for viewer in state.players:
        view = build_view(MODE, state, viewer.id)
        allowed = {PUBLIC, private(viewer.id)} | {channel(c) for c in MODE.channels_for(viewer.role)}
        assert all(e.vis in allowed for e in view.events)
        for info in view.players:
            assert info.role is None or info.id == viewer.id, f"{viewer.name} knows {info.name}'s role"
        if viewer.role == SPY:
            assert not any(e.vis == channel(CIVILIANS) for e in view.events)
            # the rules list all twenty locations; legal guesses list all twenty (or the shortlist)
            body = view.model_dump(exclude={"rules", "legal_actions"})
            assert loc not in json.dumps(body), f"the spy's view names {loc}"
            guesses = [a for a in view.legal_actions if a.startswith(GUESS)]
            assert guesses == [] or len(guesses) in (len(LOCATION_NAMES), MODE.options["shortlist_size"])
            dynamic = observation(view, CAST[0], "spy_guess" if state.phase == "ask" else "vote")
            assert loc not in dynamic
            assert view.intent is None or loc not in json.dumps(view.intent)
        else:
            assert any(e.kind == "location" and loc in e.text for e in view.events), "a civilian must see it"


@pytest.mark.parametrize("shortlist", [False, True])
def test_spy_never_sees_the_location(shortlist):
    MODE.options["last_chance_shortlist"] = shortlist
    try:
        for seed in range(200):
            play_spy(seed, n=5 + seed % 4, on_step=check_views, guess_rate=0.02)
    finally:
        MODE.options["last_chance_shortlist"] = False


def test_the_shortlist_holds_the_true_location_and_decoys():
    from engine.modes.spy_location import shortlist

    state = play_spy(3, n=6)
    picks = shortlist(state)
    assert len(picks) == 5 == len(set(picks)) and location(state) in picks
