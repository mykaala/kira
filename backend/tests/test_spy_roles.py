"""Location roles (the `roles` option): the deal, who can see a role, the prompts, the title retry, the angle,
and the human's view. With roles off nothing changes (test_spy_k1_parity.py replays the recorded games)."""

import asyncio
import json
import os

os.environ["FAKE_LLM"] = "1"

import pytest  # noqa: E402
from spy_bots import NAMES, play_spy  # noqa: E402
from test_spy_agents import CHARS_PER_TOKEN, Scripted, civilian_answerer, runner  # noqa: E402
from test_spy_live import make_runner, new_live, play  # noqa: E402

from agents.personas import CAST  # noqa: E402
from agents.spy_fake import SpyFakeLLM  # noqa: E402
from agents.spy_prompt import observation, own_role, shared_block  # noqa: E402
from agents.spy_runner import TITLE_RETRY  # noqa: E402
from engine.engine import new_game  # noqa: E402
from engine.modes.spy_location import (  # noqa: E402
    ANGLES,
    CIVILIAN,
    PLACE_ROLE,
    SPY,
    SPY_MODE,
    configure,
    deal_roles,
    location,
    place_role,
)
from engine.modes.spy_roles import ROLES  # noqa: E402
from engine.views import build_view  # noqa: E402
from server.spy_game import SpyGame  # noqa: E402
from server.spy_live import LeakWarning  # noqa: E402


@pytest.fixture
def roles_on():
    before = dict(SPY_MODE.options)
    configure(roles=True)
    yield
    configure(**before)


def titles(state) -> dict[str, str]:
    return {e.target: e.text for e in state.events if e.kind == PLACE_ROLE}


def test_each_civilian_gets_a_distinct_role_and_the_spy_none(roles_on):
    for seed in range(300):
        n = 5 + seed % 4
        s = new_game(SPY_MODE, NAMES[:n], None, seed)
        got = titles(s)
        civilians = {p.id for p in s.players if p.role == CIVILIAN}
        assert set(got) == civilians and len(set(got.values())) == len(civilians)
        bank = {r["title"]: r for r in ROLES[location(s)]}
        assert all(t in bank for t in got.values())
        assert sum(bank[t]["generic"] for t in got.values()) >= 2  # min_generic_roles_per_game
        assert all(e.vis == f"private:{e.target}" for e in s.events if e.kind == PLACE_ROLE)
        assert got == deal_roles(seed, location(s), sorted(civilians, key=lambda p: int(p[1:])), 2)  # seed+"roles"


def test_min_generic_roles_is_a_floor_and_roles_off_deals_nothing(roles_on):
    configure(min_generic_roles_per_game=4)
    for seed in range(100):
        s = new_game(SPY_MODE, NAMES[:8], None, seed)
        bank = {r["title"]: r for r in ROLES[location(s)]}
        generic = sum(r["generic"] for r in ROLES[location(s)])
        assert sum(bank[t]["generic"] for t in titles(s).values()) >= min(4, generic)
    configure(roles=False)
    assert not titles(new_game(SPY_MODE, NAMES[:6], None, 1))


def test_only_the_owner_sees_their_role(roles_on):
    for seed in range(50):
        s = play_spy(seed, n=5 + seed % 4)
        for viewer in s.players:
            seen = [e for e in build_view(SPY_MODE, s, viewer.id).events if e.kind == PLACE_ROLE]
            assert [e.target for e in seen] == ([viewer.id] if viewer.role == CIVILIAN else [])


def test_the_persons_chosen_role_moves_the_role_card_with_the_civilian_seat(roles_on, tmp_path):
    for seed in range(40):
        for role in (SPY, CIVILIAN):
            g = new_live(tmp_path, role=role, seed=seed, players=6)
            civilians = {p.id for p in g.state.players if p.role == CIVILIAN}
            assert set(titles(g.state)) == civilians
            assert (g.human in titles(g.state)) == (role == CIVILIAN)


async def test_shared_block_with_roles_is_identical_for_everyone_and_holds_no_role(roles_on, tmp_path):
    s, _ = civilian_answerer(3)
    seen = set()
    for call_type in ("vote", "ask", "spy_guess", "answer", "last_chance"):
        for p in s.players:
            rec = Scripted({"target": "nobody"}, {"target": "nobody"})
            await runner(rec, tmp_path).play(
                game_id="g", view=build_view(SPY_MODE, s, p.id), persona=CAST[0], call_type=call_type
            )
            seen.add(rec.calls[0]["messages"][0]["content"])
    block = shared_block(SPY_MODE.rules, True)
    assert seen == {block} and block != shared_block(SPY_MODE.rules)
    assert "ROLES AT THE LOCATION" in block and "hint, not proof" in block and "Never presume one" in block
    assert "about the place, not the person" not in block
    assert len(block) / CHARS_PER_TOKEN >= 1100
    every_title = {r["title"] for rs in ROLES.values() for r in rs}
    assert not [t for t in every_title if f" {t} " in f" {block.lower()} "]


def test_prompts_carry_only_your_own_card_and_never_the_insider_tell(roles_on):
    tells = [r["insider_tell"] for rs in ROLES.values() for r in rs]
    for seed in range(40):
        s = play_spy(seed, n=6, guess_rate=0)
        for p in s.players:
            view = build_view(SPY_MODE, s, p.id)
            text = observation(view, CAST[0], "vote")
            mine = own_role(view)
            if p.role == SPY:
                assert mine is None and "You have no role at the location" in text
            else:
                assert mine == place_role(s, p.id) and f"(secret; never say this title): {mine['title']}." in text
                assert mine["wears"] in text and "insider_tell" not in mine
                others = {t for pid, t in titles(s).items() if pid != p.id}
                assert not [t for t in others if f"): {t}." in text]
            assert not any(t in text for t in tells)


def test_the_angle_is_a_separate_seeded_draw(roles_on):
    def plans(angle: bool) -> list:
        configure(ask_angle=angle)
        out = []
        play_spy(5, n=7, on_step=lambda s: out.extend(SPY_MODE.intent(s, p) for p in s.players if s.phase == "ask"))
        return out

    without, with_angle = plans(False), plans(True)
    assert [x and x.get("plan") for x in without] == [x and x.get("plan") for x in with_angle]  # same plans
    angles = [x["angle"] for x in with_angle if x]
    assert angles and set(angles) <= set(ANGLES) and not any(x and "angle" in x for x in without)


async def test_a_civilian_saying_their_role_title_is_retried(roles_on, tmp_path):
    s, target = civilian_answerer()
    mine = place_role(s, target)
    rec = Scripted({"text": f"as a {mine['title']} honestly the hours"}, {"text": "the hours are rough ngl"})
    turn = await runner(rec, tmp_path).play(
        game_id="g", view=build_view(SPY_MODE, s, target), persona=CAST[0], call_type="answer"
    )
    assert turn.move == {"text": "the hours are rough ngl"} and turn.title_first and not turn.leaked_first
    assert TITLE_RETRY.format(title=mine["title"]) in rec.calls[1]["messages"][-1]["content"]


async def test_the_person_sees_their_own_card_gets_a_soft_title_warning_and_results_list_roles(roles_on, tmp_path):
    calm = make_runner(tmp_path, SpyFakeLLM(seed=1, leak_rate=0, guess_rate=0))
    game = new_live(tmp_path, role=CIVILIAN, seed=5, runner=calm)
    warned = []

    def choose(g, rng):
        t = g.status["turn"]
        card = g.status["secret"]["role"]
        assert card == place_role(g.state, g.human) and set(card) == {"title", "wears", "does", "deals_with"}
        if t["type"] == "answer" and not warned:
            with pytest.raises(LeakWarning, match="your role"):
                g.submit({"type": "answer", "text": f"im the {card['title']} here"})
            warned.append(card["title"])
        from test_spy_live import default_move

        return default_move(g, rng)

    await play(game, choose)
    assert warned and game.reveal["place_roles"] == titles(game.state)
    assert set(game.reveal["place_roles"]) == {p.id for p in game.state.players if p.role == CIVILIAN}


def test_fake_games_with_roles_and_angle_finish(roles_on, tmp_path):
    configure(ask_angle=True)
    r = make_runner(tmp_path, SpyFakeLLM(seed=2))
    for seed in range(6):
        g = SpyGame(runner=r, log=r.log, players=5 + seed % 4, seed=seed)
        asyncio.run(g.run())
        assert g.state.winner or g.void
    prompts = [json.loads(p) for (p,) in r.log.db.execute("SELECT prompt FROM calls")]
    assert any("YOUR ANGLE FOR THIS QUESTION" in m[-1]["content"] for m in prompts)
    tells = [x["insider_tell"] for rs in ROLES.values() for x in rs]
    assert not any(t in json.dumps(m) for m in prompts for t in tells)


def test_each_game_keeps_its_own_switches(tmp_path):
    """Roles and the angle are per game (the lobby's Advanced section): two games side by side, the mode's own
    defaults untouched, and a later configure() can't change a game that is already running."""
    before = dict(SPY_MODE.options)
    on = new_live(tmp_path, role=CIVILIAN, seed=3, options={"roles": True, "ask_angle": True})
    off = new_live(tmp_path, role=CIVILIAN, seed=3, options={"roles": False})
    assert SPY_MODE.options == before
    assert titles(on.state) and not titles(off.state)
    assert "secret role at the location" in build_view(SPY_MODE, on.state, on.human).rules
    assert "secret role at the location" not in build_view(SPY_MODE, off.state, off.human).rules
    assert on.state.options["ask_angle"] and on.state.options == on.options == SPY_MODE.options | on.options
    configure(roles=True)
    try:
        assert not titles(off.state) and build_view(SPY_MODE, off.state, off.human).options["roles"] is False
    finally:
        configure(**before)


def test_the_lobby_defaults_are_roles_on_and_angle_off(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from server import app as app_module

    r = make_runner(tmp_path)
    monkeypatch.setattr(app_module, "get_spy_runner", lambda: r)
    app_module.started.clear()
    with TestClient(app_module.app) as c:
        gid = c.post("/api/spy/games", json={"name": "Alex", "role": "civilian", "seed": 4}).json()["game_id"]
        g = app_module.games[gid]
        assert g.state.options["roles"] is True and g.state.options["ask_angle"] is False and titles(g.state)
        gid2 = c.post("/api/spy/games", json={"name": "Alex", "seed": 4, "roles": False, "ask_angle": True}).json()
        g2 = app_module.games[gid2["game_id"]]
        assert g2.state.options["roles"] is False and g2.state.options["ask_angle"] is True
        assert {"roles", "ask_angle"} <= set(c.get("/api/spy/config").json()["options"])
        for x in (g, g2):
            x.task.cancel()


def test_a_generic_floor_above_what_a_place_has_degrades_gracefully(tmp_path, monkeypatch, caplog):
    """A place with fewer generic roles than min_generic_roles_per_game deals all it has, logs it, and plays on;
    even a bank smaller than the table never crashes (the last civilians just get no role)."""
    import logging

    from engine.modes import spy_location

    s = new_game(SPY_MODE, NAMES[:8], None, 11)
    place = location(s)
    thin = [dict(r, generic=i == 0) for i, r in enumerate(ROLES[place])]  # one generic role only
    monkeypatch.setitem(spy_location.ROLES, place, thin)
    civilians = [f"p{i}" for i in range(7)]
    dealt = deal_roles(11, place, civilians, 5)
    assert len(dealt) == 7 and len(set(dealt.values())) == 7 and thin[0]["title"] in dealt.values()
    assert spy_location.generic_shortfall(place, 7, 5) == 4 and spy_location.generic_shortfall(place, 7, 1) == 0
    assert spy_location.generic_shortfall(place, 2, 5) == 1  # the floor never exceeds the civilians
    monkeypatch.setitem(spy_location.ROLES, place, thin[:3])  # fewer roles than civilians
    assert len(deal_roles(11, place, civilians, 5)) == 3
    assert deal_roles(11, place, civilians, -1) and deal_roles(11, "nowhere", civilians, 2) == {}
    monkeypatch.setitem(spy_location.ROLES, place, thin)
    with caplog.at_level(logging.WARNING, logger="kira.spy"):
        g = SpyGame(runner=make_runner(tmp_path), log=make_runner(tmp_path).log, players=8, seed=11,
                    options={"roles": True, "min_generic_roles_per_game": 5})  # fmt: skip
        asyncio.run(g.run())
    assert g.role_shortfall == 4 and "fewer than min_generic_roles_per_game=5" in caplog.text
    assert g.state.winner or g.void
