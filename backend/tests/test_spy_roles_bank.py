"""The reviewed role bank keeps the generator's rules: ten roles per place, short titles that name no place and
copy no borrowed role name, titles unique within a place, and at least three generic roles per place."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from spy_roles_gen import FIELDS, problems  # noqa: E402

from engine.modes.spy_location import LOCATION_NAMES  # noqa: E402
from engine.modes.spy_roles import ROLES  # noqa: E402


def test_every_place_has_a_valid_role_bank():
    assert sorted(ROLES) == LOCATION_NAMES
    for place, roles in ROLES.items():
        assert problems(roles) == [], place
        assert all(set(r) == {*FIELDS, "generic"} for r in roles)
