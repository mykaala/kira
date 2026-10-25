"""The spy's view never contains the location (until the game is over), and no view shows another
player's role, with one exception: a player voted out is publicly shown to have been a civilian. The location
reaches civilians only, on their channel."""

import json

import pytest
from spy_bots import play_spy

from agents.personas import CAST
from agents.spy_prompt import observation
from engine.models import PUBLIC, channel, private
from engine.modes.spy_location import CIVILIAN, CIVILIANS, GUESS, LOCATION_NAMES, SPY, SPY_MODE, location
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
            if not info.alive:  # voted out: only ever a civilian, and only that is shown
                assert info.role == CIVILIAN and state.player(info.id).role == CIVILIAN
                continue
            assert info.role is None or info.id == viewer.id, f"{viewer.name} knows {info.name}'s role"
        if viewer.role == SPY:
            assert not any(e.vis == channel(CIVILIANS) for e in view.events)
            # the rules list every location; legal guesses list every one (or the shortlist)
            body = view.model_dump(exclude={"rules", "legal_actions"})
            assert loc not in json.dumps(body), f"the spy's view names {loc}"
            guesses = [a for a in view.legal_actions if a.startswith(GUESS)]
            assert guesses == [] or len(guesses) - 1 in (len(LOCATION_NAMES), MODE.options["shortlist_size"])
            dynamic = observation(view, CAST[0], "spy_guess" if state.phase == "ask" else "vote")
            assert loc not in dynamic
            assert view.intent is None or loc not in json.dumps(view.intent)
        else:
            assert any(e.kind == "location" and loc in e.text for e in view.events), "a civilian must see it"


@pytest.mark.parametrize("shortlist", [False, True])
def test_spy_never_sees_the_location(shortlist):
    MODE.options["last_chance_shortlist"] = shortlist
    try:
        out = 0
        for seed in range(200):
            state = play_spy(seed, n=5 + seed % 4, on_step=check_views, guess_rate=0.02)
            out += sum(not p.alive for p in state.players)
        assert out > 20  # games with players voted out were checked
    finally:
        MODE.options["last_chance_shortlist"] = False


def test_the_shortlist_holds_the_true_location_and_decoys():
    from engine.modes.spy_location import shortlist

    state = play_spy(3, n=6)
    picks = shortlist(state)
    assert len(picks) == 5 == len(set(picks)) and location(state) in picks
