"""No player's view may contain a secret their role is not allowed to know."""

from bots import play_random
from engine.engine import MODES
from engine.models import PUBLIC, channel, private
from engine.views import build_view

MODE = MODES["mafia"]


def check_views(state):
    if state.winner:
        return
    for viewer in state.players:
        view = build_view(MODE, state, viewer.id)
        allowed = {PUBLIC, private(viewer.id)} | {channel(c) for c in MODE.channels_for(viewer.role)}
        for e in view.events:
            assert e.vis in allowed, f"{viewer.name} sees {e.vis}: {e.text}"
        for info in view.players:
            other = state.player(info.id)
            if info.role is None:
                continue
            ok = (
                info.id == viewer.id
                or (not other.alive and MODE.reveal_role_on_death)
                or (viewer.role == "mafia" and other.role == "mafia")
            )
            assert ok, f"{viewer.name} ({viewer.role}) knows {other.name} is {other.role}"
        # a role is missing only for a living player, or for a dead one when roles stay hidden on death
        for info in view.players:
            if info.role is None:
                assert state.player(info.id).alive or not MODE.reveal_role_on_death
        # claims are public, but whether they are true is not
        assert len(view.claims) == len(state.claims)
        assert all("true" not in c.model_dump() for c in view.claims)
        # only mafia and the detective get a plan; a mafia plan names only their own partners
        if view.intent:
            assert viewer.role in ("mafia", "detective")
            assert all(state.player(t).role == "mafia" for t in view.intent.get("partners", []))


def test_no_view_leaks_secrets():
    for seed in range(200):
        play_random(seed, n=7 + seed % 3, on_step=check_views)


def test_villager_never_sees_mafia_channel_or_detective_result():
    state = play_random(7, n=8)
    for p in state.players:
        if p.role != "villager":
            continue
        view = build_view(MODE, state, p.id)
        assert not any(e.kind in {"mafia_choice", "result"} for e in view.events)


def test_no_view_leaks_secrets_with_roles_revealed_on_death():
    before = MODE.reveal_role_on_death
    MODE.reveal_role_on_death = True
    try:
        for seed in range(100):
            play_random(seed, n=7 + seed % 3, on_step=check_views)
    finally:
        MODE.reveal_role_on_death = before
