import asyncio
import json

import pytest
from agents.costlog import CostLog
from agents.personas import CAST
from agents.spy_fake import SpyFakeLLM
from agents.spy_judge import judge_answers, rating
from agents.spy_prompt import shared_block
from agents.spy_runner import LEAK_RETRY, SpyRunner
from engine.engine import new_game, submit_action
from engine.modes.spy_location import ANSWER, CIVILIAN, GUESS, SPY, SPY_MODE, asker, location, spy
from engine.views import build_view
from server.settings import Settings
from server.spy_game import SpyGame
from server.spy_summary import aggregate, format_aggregate, game_summary, is_repeat

CHARS_PER_TOKEN = 4


class Scripted:
    """Replies in order, recording every call."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    async def stream(self, *, usage, **kw):
        self.calls.append(kw)
        yield json.dumps(self.replies.pop(0))


def runner(llm, tmp_path):
    settings = Settings(_env_file=None, db_path=tmp_path / "t.db")
    return SpyRunner(llm, settings, CostLog(settings.db_path))


def civilian_answerer(seed=1):
    """A game where a civilian has just been asked a question."""
    s = new_game(SPY_MODE, [p.name for p in CAST[:6]], None, seed)
    target = next(p.id for p in s.players if p.role == CIVILIAN and p.id != asker(s))
    submit_action(s, asker(s), target, text="what do you hear there?")
    return s, target


async def test_shared_block_is_identical_long_and_has_no_secrets(tmp_path):
    s, _ = civilian_answerer(3)  # a question is pending, so every call type has a prompt
    seen = set()
    for call_type in ("vote", "ask", "spy_guess", "answer", "last_chance"):
        for p in s.players:
            rec = Scripted({"target": "nobody"}, {"target": "nobody"})
            await runner(rec, tmp_path).play(
                game_id="g", view=build_view(SPY_MODE, s, p.id), persona=CAST[0], call_type=call_type
            )
            assert rec.calls[0]["messages"][0]["role"] == "system"
            seen.add(rec.calls[0]["messages"][0]["content"])
    assert seen == {shared_block()}
    block = shared_block()
    assert len(block) / CHARS_PER_TOKEN >= 1100
    assert "THE LOCATION:" not in block and not any(p.name in block for p in CAST)
    assert "CIVILIAN" in block and "SPY" in block


async def test_schemas_are_fixed_per_call_type(tmp_path):
    s, target = civilian_answerer()
    r = runner(Scripted(), tmp_path)
    for call_type in ("ask", "vote", "spy_guess", "answer"):
        schemas = {json.dumps(r.schema(call_type, build_view(SPY_MODE, s, p.id))) for p in s.players}
        assert len(schemas) == 1, call_type
    assert list(r.schema("ask", build_view(SPY_MODE, s, target))["schema"]["properties"]) == ["target", "question"]


async def test_illegal_target_retries_once_then_defaults(tmp_path):
    s = new_game(SPY_MODE, [p.name for p in CAST[:6]], None, 1)
    me = asker(s)
    rec = Scripted({"target": s.player(me).name, "question": "hm?"}, {"target": "Nobody", "question": "hm?"})
    turn = await runner(rec, tmp_path).play(
        game_id="g", view=build_view(SPY_MODE, s, me), persona=CAST[0], call_type="ask"
    )
    assert turn.defaulted and len(rec.calls) == 2
    assert "not a legal target" in rec.calls[1]["messages"][-1]["content"]


async def test_a_civilian_naming_the_location_is_retried(tmp_path):
    s, target = civilian_answerer()
    loc = location(s)
    rec = Scripted({"text": f"classic {loc} stuff"}, {"text": "you can smell it before you see it"})
    turn = await runner(rec, tmp_path).play(
        game_id="g", view=build_view(SPY_MODE, s, target), persona=CAST[0], call_type="answer"
    )
    assert turn.move == {"text": "you can smell it before you see it"} and turn.leaked_first
    assert LEAK_RETRY in rec.calls[1]["messages"][-1]["content"]
    # named twice: posted anyway, so the posted leak rate sees it
    rec = Scripted({"text": f"{loc} obviously"}, {"text": f"the {loc} lol"})
    turn = await runner(rec, tmp_path).play(
        game_id="g", view=build_view(SPY_MODE, s, target), persona=CAST[0], call_type="answer"
    )
    assert turn.move == {"text": f"the {loc} lol"} and not turn.defaulted


async def test_spy_guess_null_means_keep_playing_but_not_at_the_last_chance(tmp_path):
    s = new_game(SPY_MODE, [p.name for p in CAST[:6]], None, 1)
    sp = spy(s).id
    if asker(s) != sp:
        submit_action(s, asker(s), sp, text="q?")
        submit_action(s, sp, ANSWER, text="a")
    turn = await runner(Scripted({"location": None}), tmp_path).play(
        game_id="g", view=build_view(SPY_MODE, s, sp), persona=CAST[0], call_type="spy_guess"
    )
    assert turn.move == {"location": None}
    view = build_view(SPY_MODE, s, sp)
    view.phase, view.legal_actions = "last_chance", [a for a in view.legal_actions if a.startswith(GUESS)]
    turn = await runner(Scripted({"location": None}, {"location": None}), tmp_path).play(
        game_id="g", view=view, persona=CAST[0], call_type="last_chance"
    )
    assert turn.defaulted


@pytest.mark.parametrize("seat", ["ai", "bot"])
async def test_fake_games_run_end_to_end_and_summarize(tmp_path, seat):
    settings = Settings(_env_file=None, db_path=tmp_path / "t.db", fake_llm=True)
    log = CostLog(settings.db_path)
    llm = SpyFakeLLM(seed=4)
    r = SpyRunner(llm, settings, log)
    games = []
    for i in range(8):
        g = SpyGame(runner=r, log=log, players=5 + i % 4, human_seat=seat, seed=100 + i)
        await g.run()
        assert g.state.winner in (SPY, "civilians") and not g.aborted and not g.defaulted
        humans = [p for p in g.state.players if p.is_human]
        assert [p.name for p in humans] == (["Sam"] if seat == "bot" else [])
        games.append(game_summary(log, g, seat, {}))
    items = [(g, a) for g in games for a in g["answers"] if a["role"] == CIVILIAN]
    rated = await judge_answers(llm, settings, log, [{"game_id": g["game_id"], **a} for g, a in items])
    for (_, a), res in zip(items, rated):
        a.update(res)
    agg = aggregate(log, games)
    assert agg["games"] == 8 and agg["specificity"]["judged"] == len(items)
    assert {"ask", "answer", "vote", "judge"} <= set(agg["calls"])
    assert "spy win rate" in format_aggregate(agg)


def test_same_seed_same_fake_game(tmp_path):
    def play(d):
        settings = Settings(_env_file=None, db_path=tmp_path / f"{d}.db", fake_llm=True)
        log = CostLog(settings.db_path)
        g = SpyGame(runner=SpyRunner(SpyFakeLLM(seed=9), settings, log), log=log, players=7, seed=77)
        asyncio.run(g.run())
        return [e.model_dump() for e in g.state.events]

    assert play("a") == play("b")


def test_rating_buckets_and_repeats():
    assert [rating(n) for n in (0, 1, 2, 3, 5, 9, 15, 20)] == [None, 5, 4, 4, 3, 2, 1, 1]
    assert is_repeat("what do u wear here?", ["What do you wear here"])
    assert is_repeat("how long do people stay?", ["how long do people usually stay"])
    assert not is_repeat("what's the smell like", ["how loud is it"])
