import asyncio
import json

import pytest
from agents.costlog import CostLog
from agents.personas import CAST
from agents.spy_fake import SpyFakeLLM
from agents.spy_judge import judge_answers, rating
from agents.spy_prompt import observation, shared_block
from agents.spy_runner import LEAK_RETRY, SpyRunner
from engine.engine import new_game, submit_action
from engine.modes.spy_location import CLUSTERS, LOCATIONS, ANSWER, CIVILIAN, GUESS, SPY, SPY_MODE, asker, location, spy
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
        reply = self.replies.pop(0)
        yield reply if isinstance(reply, str) else json.dumps(reply)  # a str is sent as is ("" = empty reply)


def runner(llm, tmp_path):
    settings = Settings(_env_file=None, db_path=tmp_path / "t.db")
    return SpyRunner(llm, settings, CostLog(settings.db_path), memo_path=tmp_path / "memo.json")


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
    block = shared_block(SPY_MODE.rules)
    assert seen == {block}
    assert "call_vote" not in block and "call a vote" not in block.lower()
    assert len(block) / CHARS_PER_TOKEN >= 1100
    assert "THE LOCATION:" not in block and not any(p.name in block for p in CAST)
    assert "CIVILIAN" in block and "SPY" in block


async def test_schemas_are_fixed_per_call_type(tmp_path):
    s, target = civilian_answerer()
    r = runner(Scripted(), tmp_path)
    for call_type in ("ask", "vote", "spy_guess", "answer"):
        schemas = {json.dumps(r.schema(call_type, build_view(SPY_MODE, s, p.id))) for p in s.players}
        assert len(schemas) == 1, call_type
    ask = r.schema("ask", build_view(SPY_MODE, s, target))["schema"]["properties"]
    assert list(ask) == ["target", "question"]


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
    turn = await runner(Scripted({"guess": None}), tmp_path).play(
        game_id="g", view=build_view(SPY_MODE, s, sp), persona=CAST[0], call_type="spy_guess"
    )
    assert turn.move == {"guess": None}
    view = build_view(SPY_MODE, s, sp)
    view.phase, view.legal_actions = "last_chance", [a for a in view.legal_actions if a.startswith(GUESS)]
    rec = Scripted({"guess": None}, {"guess": "a sauna or a pool"})
    turn = await runner(rec, tmp_path).play(game_id="g", view=view, persona=CAST[0], call_type="last_chance")
    assert turn.defaulted and "not allowed" in rec.calls[1]["messages"][-1]["content"]
    # free text, legal: one place in at most 6 words
    turn = await runner(Scripted({"guess": "  The Aquarium "}), tmp_path).play(
        game_id="g", view=view, persona=CAST[0], call_type="last_chance"
    )
    assert turn.move == {"guess": "The Aquarium"}
    assert rec.calls[0]["max_tokens"] == 800 and "enum" not in json.dumps(rec.calls[0]["schema"])


async def test_an_empty_guess_reply_is_retried_then_a_pass(tmp_path):
    s = new_game(SPY_MODE, [p.name for p in CAST[:6]], None, 1)
    view = build_view(SPY_MODE, s, spy(s).id)
    turn = await runner(Scripted("", {"guess": "sauna"}), tmp_path).play(
        game_id="g", view=view, persona=CAST[0], call_type="spy_guess"
    )
    assert turn.move == {"guess": "sauna"} and not turn.empty
    turn = await runner(Scripted("", ""), tmp_path).play(game_id="g", view=view, persona=CAST[0], call_type="spy_guess")
    assert turn.empty and turn.move is None and not turn.defaulted


async def test_an_empty_last_chance_voids_the_game(tmp_path):
    settings = Settings(_env_file=None, db_path=tmp_path / "t.db")
    log = CostLog(settings.db_path)

    class EmptyAtLastChance(SpyFakeLLM):
        async def stream(self, *, schema, **kw):
            if schema["name"] == "guess" and "caught you" in kw["messages"][-1]["content"]:
                yield ""
                return
            async for chunk in super().stream(schema=schema, **kw):
                yield chunk

    r = SpyRunner(EmptyAtLastChance(seed=1, guess_rate=0), settings, log, memo_path=tmp_path / "m.json")
    voided = 0
    for seed in range(30):
        g = SpyGame(runner=r, log=log, players=5, seed=seed)
        await g.run()
        if any(e.kind == "accused" and "is the spy" in e.text for e in g.state.events):
            assert g.void and g.state.winner is None
            voided += 1
    assert voided  # some vote landed on the spy


@pytest.mark.parametrize("seat", ["ai", "bot"])
async def test_fake_games_run_end_to_end_and_summarize(tmp_path, seat):
    settings = Settings(_env_file=None, db_path=tmp_path / "t.db", fake_llm=True)
    log = CostLog(settings.db_path)
    llm = SpyFakeLLM(seed=4)
    r = SpyRunner(llm, settings, log, memo_path=tmp_path / "memo.json")
    games = []
    for i in range(8):
        g = SpyGame(runner=r, log=log, players=5 + i % 4, human_seat=seat, seed=100 + i)
        await g.run()
        assert g.state.winner in (SPY, "civilians", "draw") and not g.aborted and not g.defaulted
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
        g = SpyGame(
            runner=SpyRunner(SpyFakeLLM(seed=9), settings, log, memo_path=tmp_path / f"{d}-memo.json"),
            log=log,
            players=7,
            seed=77,
        )
        asyncio.run(g.run())
        return [e.model_dump() for e in g.state.events]

    assert play("a") == play("b")


def test_rating_buckets_and_repeats():
    assert [rating(n) for n in (0, 1, 2, 3, 5, 9, 15, 20)] == [None, 5, 4, 4, 3, 2, 1, 1]
    assert is_repeat("what do u wear here?", ["What do you wear here"])
    assert is_repeat("how long do people stay?", ["how long do people usually stay"])
    assert not is_repeat("what's the smell like", ["how loud is it"])


def test_giveaway_matcher_uses_place_and_cluster_words_with_stems():
    from agents.spy_giveaways import _lists, giveaway

    places, clusters = _lists()
    assert set(places) == set(LOCATIONS) and set(clusters) == set(CLUSTERS)
    assert all(set([p, *LOCATIONS[p]]) <= set(places[p]) for p in LOCATIONS)  # aliases are in
    assert giveaway("the CHLORINE gets everywhere", "swimming pool") == "chlorine"
    assert giveaway("so many snowflakes", "ski lodge") == "snowflake"  # cluster word, plural
    assert giveaway("we went figure skating", "ice rink") == "figure skate"  # skate -> skating
    assert giveaway("roller skates for rent", "roller rink")
    assert giveaway("depends on the day", "swimming pool") is None
    assert giveaway("a bag of chlorinated stuff", "ski lodge") is None  # another cluster's word


async def test_a_civilian_giveaway_is_retried_with_the_word(tmp_path, monkeypatch):
    monkeypatch.setitem(SPY_MODE.options, "giveaway_check", True)  # off by default
    s, target = civilian_answerer()
    from agents.spy_giveaways import _lists

    word = next(w for w in _lists()[0][location(s)] if " " not in w and w not in location(s))
    rec = Scripted({"text": f"honestly the {word} lol"}, {"text": "depends who you ask"})
    turn = await runner(rec, tmp_path).play(
        game_id="g", view=build_view(SPY_MODE, s, target), persona=CAST[0], call_type="answer"
    )
    assert turn.move == {"text": "depends who you ask"} and turn.giveaway_first
    assert (
        f"Your answer contains {turn.giveaway_first}, which gives the place away."
        in (rec.calls[1]["messages"][-1]["content"])
    )


def test_guess_rules_in_order():
    from agents.spy_guess import deterministic

    assert deterministic("Swimming Pools!", "swimming pool") == (True, "exact")
    assert deterministic("veterinary clinic", "vet clinic") == (True, "alias")
    assert deterministic("a big public swimming pool", "swimming pool") == (True, "modifier")
    assert deterministic("planetarum", "planetarium") == (True, "typo")  # one edit, 6+ letters
    assert deterministic("sana", "sauna") is None  # short words get no typo slack
    assert deterministic("ski lodge", "mountain hut") == (False, "other_place")
    assert deterministic("airport", "airport lounge") == (False, "partial")
    assert deterministic("somewhere with water", "swimming pool") is None  # left to the judge


async def test_judge_verdicts_are_remembered_across_matchers(tmp_path):
    from agents.spy_guess import GuessMatcher

    settings = Settings(_env_file=None, db_path=tmp_path / "t.db")
    log, memo = CostLog(settings.db_path), tmp_path / "memo.json"
    first = GuessMatcher(Scripted({"reason": "different", "match": False}), settings, log, memo)
    d = await first.decide(game_id="g", guess="A gym", truth="sauna")
    assert (d.match, d.rule) == (False, "judge") and memo.exists()
    again = GuessMatcher(Scripted(), settings, log, memo)  # no replies left: must not call the judge
    d = await again.decide(game_id="g", guess="gym", truth="sauna")
    assert (d.match, d.rule, d.reason) == (False, "judge_memo", "different")
    failing = GuessMatcher(Scripted("", ""), settings, log, tmp_path / "m2.json")
    d = await failing.decide(game_id="g", guess="a gym", truth="sauna")
    assert (d.match, d.rule) == (False, "judge_failed") and not (tmp_path / "m2.json").exists()


def test_prompts_list_only_players_still_in_and_where_the_game_stands():
    from spy_bots import play_spy

    from engine.engine import pending
    from engine.modes.spy_location import configure
    from engine.views import build_view

    before = dict(SPY_MODE.options)
    configure(spy_survive_votes=3)
    seen = []

    def check(state):
        out = [p for p in state.players if not p.alive]
        if not out or state.phase not in ("ask", "vote"):
            return
        for r in pending(state):
            view = build_view(SPY_MODE, state, r.pid)
            text = observation(view, CAST[0], "vote" if state.phase == "vote" else "ask")
            table = text.split("PLAYERS AT THE TABLE: ")[1].split("\n")[0]
            assert all(p.name not in table.split(", ") for p in out)
            assert f"VOTED OUT (known civilians, out of the game): {', '.join(p.name for p in out)}" in text
            legal = json.loads(text.split("Legal `target` values: ")[1].split("\n")[0])
            assert not {p.name for p in out} & set(legal)
            assert "WHERE THE GAME STANDS: round" in text
            if state.phase == "vote":
                assert "Time to vote (round " in text
            seen.append(state.phase)

    try:
        for seed in range(20):
            play_spy(seed, n=6, on_step=check, guess_rate=0)
        configure(spy_survive_votes=1)
        state = play_spy(1, n=6, guess_rate=0)
        view = build_view(SPY_MODE, state, state.players[0].id)
        assert "WHERE THE GAME STANDS" not in observation(view, CAST[0], "vote")  # the single-vote prompt as before
    finally:
        configure(**before)
    assert {"ask", "vote"} <= set(seen)
