"""With spy_survive_votes=1 the multi-round rules must replay the single-vote game exactly: the same asks,
answers, votes, guesses and outcomes on the same seeds as the recorded fingerprints (tests/spy_fingerprint.py,
recorded before the rule change)."""

import json

import pytest
from spy_fingerprint import FILE, record

from engine.modes.spy_location import SPY_MODE, configure


@pytest.fixture
def single_vote():
    before = dict(SPY_MODE.options)
    configure(spy_survive_votes=1)
    yield
    configure(**before)


def test_one_vote_replays_the_recorded_games(single_vote):
    want, got = json.loads(FILE.read_text()), record()
    assert want.keys() == got.keys()
    for arm in want:
        for i, (w, g) in enumerate(zip(want[arm], got[arm], strict=True)):
            assert g == w, f"{arm} game {i} differs"
