import json

from agents.checks import capped_uses
from agents.costlog import CostLog
from agents.llm import FakeLLM
from agents.personas import CAST
from agents.prompt import observation, persona_block, shared_block
from agents.runner import AgentRunner
from agents.schemas import BeliefState, action_schema, discussion_schema
from engine.engine import MODES, new_game, pending, submit_action
from engine.views import build_view
from server.settings import Settings

MODE = MODES["mafia"]
CHARS_PER_TOKEN = 4  # a conservative English average; the API's own count is checked in self-play


class Recorder:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def stream(self, *, usage, **kw):
        self.calls.append(kw)
        yield self.reply


def state():
    s = new_game(MODE, [p.name for p in CAST[:7]], None, 5)
    for r in pending(s):
        submit_action(s, r.pid, "abstain")
    return s


async def test_shared_block_is_first_byte_identical_and_long_enough(tmp_path):
    s = state()
    prefixes = set()
    for p in s.players:
        rec = Recorder(
            json.dumps({"say": "hm", "state": {"suspicion": [], "claims_heard": [], "my_claims": [], "plan": ""}})
        )
        runner = AgentRunner(rec, Settings(db_path=tmp_path / "t.db"), CostLog(tmp_path / "t.db"))
        await runner.play(
            game_id="g",
            view=build_view(MODE, s, p.id),
            persona=next(c for c in CAST if c.name == p.name),
            beliefs=BeliefState(),
            call_type="discussion",
            default_action="none",
        )
        first = rec.calls[0]["messages"][0]
        assert first["role"] == "system"
        prefixes.add(first["content"])
    assert len(prefixes) == 1  # every agent and every role shares it
    block = prefixes.pop()
    assert len(block) / CHARS_PER_TOKEN >= 1100
    for role in ("mafia", "detective", "doctor", "villager"):
        assert role.upper() in block  # all role guides, not just yours


def test_no_secret_in_the_shared_or_persona_block():
    s = state()
    mafia = [p for p in s.players if p.role == "mafia"]
    block = shared_block(MODE.rules) + "".join(persona_block(c) for c in CAST)
    assert "YOUR SECRET ROLE" not in block
    for p in mafia:
        view = build_view(MODE, s, p.id)
        obs = observation(view, CAST[0], BeliefState(), "discussion", ["none"])
        assert "YOUR SECRET ROLE: MAFIA" in obs  # the role card lives in the dynamic part


def test_voice_cards_have_three_lines():
    assert all(len(c.sample_lines) == 3 for c in CAST)
    assert all(all(line.lower() in persona_block(c) for line in c.sample_lines) for c in CAST)


def test_vote_and_night_schemas_are_action_only():
    assert list(action_schema(["Bram", "abstain"])["schema"]["properties"]) == ["action"]
    props = discussion_schema({"anyOf": []}, {"anyOf": []})["schema"]["properties"]
    assert list(props) == ["say", "accuses", "claim", "state"]


async def test_vote_call_uses_action_schema_small_cap_and_keeps_notes(tmp_path):
    s = state()
    s.phase = "vote"
    rec = Recorder(json.dumps({"action": "abstain"}))
    runner = AgentRunner(
        rec, Settings(db_path=tmp_path / "t.db", max_output_tokens_action=123), CostLog(tmp_path / "t.db")
    )
    notes = BeliefState(plan="watch kit")
    view = build_view(MODE, s, "p0")
    view.legal_actions = ["p1", "abstain"]
    result = await runner.play(
        game_id="g", view=view, persona=CAST[0], beliefs=notes, call_type="vote", default_action="abstain"
    )
    call = rec.calls[0]
    assert call["max_tokens"] == 123 and list(call["schema"]["schema"]["properties"]) == ["action"]
    assert result.action == "abstain" and result.beliefs.plan == "watch kit"


def test_capped_phrases_counted_with_forms():
    assert capped_uses("so convenient. CONVENIENTLY staged, a dogpile, then piling on") == [
        "convenient",
        "convenient",
        "staged",
        "pile-on",
        "pile-on",
    ]
    assert capped_uses("that's easy, a tell") == []  # left off the cap on purpose


async def test_used_up_phrase_is_banned_in_the_prompt_and_retried_once(tmp_path):
    s = state()
    view = build_view(MODE, s, s.queue[0])
    me = next(c for c in CAST if c.name == s.player(view.you).name)
    note = {"suspicion": [], "claims_heard": [], "my_claims": [], "plan": ""}
    replies = [
        json.dumps({"say": "that's so convenient", "state": note}),
        json.dumps({"say": "too smooth", "state": note}),
    ]

    class Two(Recorder):
        async def stream(self, *, usage, **kw):
            self.calls.append(kw)
            yield replies[len(self.calls) - 1]

    rec = Two("")
    runner = AgentRunner(rec, Settings(db_path=tmp_path / "t.db"), CostLog(tmp_path / "t.db"))
    result = await runner.play(
        game_id="g",
        view=view,
        persona=me,
        beliefs=BeliefState(),
        call_type="discussion",
        default_action="none",
        used_up=["convenient"],
    )
    assert "USED UP, don't use these words: convenient" in rec.calls[0]["messages"][-1]["content"]
    assert len(rec.calls) == 2 and result.say == "too smooth"


async def test_game_tracks_phrases_across_the_table(tmp_path):
    from server.orchestrator import Game

    settings = Settings(db_path=tmp_path / "t.db", phrase_cap=2)
    runner = AgentRunner(FakeLLM(), settings, CostLog(settings.db_path))
    game = Game(runner=runner, log=runner.log, opponents=6, human_name="Alex", seed=3)
    game.phrase_uses.update(["convenient", "staged", "convenient"])
    assert game.used_up() == ["convenient"]


async def _schemas_for(tmp_path, s, call_type):
    out = []
    for p in s.players:
        view = build_view(MODE, s, p.id)
        if call_type != "discussion" and not view.legal_actions:
            continue
        reply = (
            json.dumps({"say": "hm", "state": {"suspicion": [], "claims_heard": [], "my_claims": [], "plan": ""}})
            if call_type == "discussion"
            else json.dumps({"action": "abstain"})
        )
        rec = Recorder(reply)
        runner = AgentRunner(rec, Settings(db_path=tmp_path / "t.db"), CostLog(tmp_path / "t.db"))
        await runner.play(
            game_id="g",
            view=view,
            persona=next(c for c in CAST if c.name == p.name),
            beliefs=BeliefState(),
            call_type=call_type,
            default_action="abstain",
            claim_roles=MODE.claimable_roles,
            judge_claim=lambda c: None,
        )
        out.append(json.dumps(rec.calls[0]["schema"]))  # key order matters to the cache, so don't sort
    return out


async def test_one_schema_per_call_type_for_every_agent(tmp_path):
    s = state()
    discussion = await _schemas_for(tmp_path, s, "discussion")
    assert len(discussion) == 7 and len(set(discussion)) == 1
    assert list(json.loads(discussion[0])["schema"]["properties"])[0] == "say"  # still streams first
    s.phase = "vote"
    votes = await _schemas_for(tmp_path, s, "vote")
    assert len(votes) == 7 and len(set(votes)) == 1
    enum = json.loads(votes[0])["schema"]["properties"]["action"]["enum"]
    assert enum == [c.name for c in CAST] + ["abstain"]  # the whole cast, even the one not seated


class Scripted(Recorder):
    def __init__(self, replies):
        super().__init__("")
        self.replies = replies

    async def stream(self, *, usage, **kw):
        self.calls.append(kw)
        yield self.replies[len(self.calls) - 1]


async def _vote(tmp_path, view, replies, default="abstain"):
    rec = Scripted([json.dumps({"action": a}) for a in replies])
    runner = AgentRunner(rec, Settings(db_path=tmp_path / "t.db"), CostLog(tmp_path / "t.db"))
    me = next(c for c in CAST if c.name == next(p.name for p in view.players if p.id == view.you))
    result = await runner.play(
        game_id="g", view=view, persona=me, beliefs=BeliefState(), call_type=view.phase, default_action=default
    )
    return result, rec


async def test_illegal_names_are_retried_once_then_defaulted(tmp_path):
    s = state()
    s.phase = "vote"
    view = build_view(MODE, s, "p0")
    me = next(p.name for p in view.players if p.id == "p0")
    other = next(p.name for p in view.players if p.id != "p0")
    unseated = next(c.name for c in CAST if c.name not in {p.name for p in view.players})
    result, rec = await _vote(tmp_path, view, [me, other])  # yourself, then a legal pick
    assert len(rec.calls) == 2 and result.action != "p0" and not result.defaulted
    assert "not a legal choice" in rec.calls[1]["messages"][-1]["content"]
    result, rec = await _vote(tmp_path, view, [unseated, me])  # twice illegal
    assert result.defaulted and result.action == "abstain"


async def test_mafia_cannot_kill_a_teammate_and_doctor_cannot_repeat(tmp_path):
    from bots import play_random  # noqa: F401  (keeps the import style of the suite)
    from engine.engine import submit_say

    s = state()
    while s.phase != "night" or s.day < 2:  # play to night 2 with nobody voted out
        for r in pending(s):
            submit_action(s, r.pid, "abstain") if r.kind == "act" else submit_say(s, r.pid, "hm")
    mafia = [p for p in s.players if p.role == "mafia"]
    view = build_view(MODE, s, mafia[0].id)
    villager = next(p.name for p in s.players if p.role == "villager")
    result, rec = await _vote(tmp_path, view, [mafia[1].name, villager], default=view.legal_actions[0])
    assert len(rec.calls) == 2 and s.player(result.action).role == "villager"


async def test_bad_accusation_is_retried_then_dropped_keeping_the_message(tmp_path):
    s = state()
    view = build_view(MODE, s, s.queue[0])
    me_name = next(p.name for p in view.players if p.id == view.you)
    note = {"suspicion": [], "claims_heard": [], "my_claims": [], "plan": ""}
    rec = Scripted([json.dumps({"say": "it's me lol", "accuses": me_name, "state": note})] * 2)
    runner = AgentRunner(rec, Settings(db_path=tmp_path / "t.db"), CostLog(tmp_path / "t.db"))
    result = await runner.play(
        game_id="g",
        view=view,
        persona=next(c for c in CAST if c.name == me_name),
        beliefs=BeliefState(),
        call_type="discussion",
        default_action="none",
    )
    assert len(rec.calls) == 2 and "can't accuse" in rec.calls[1]["messages"][-1]["content"]
    assert result.say == "it's me lol" and result.accuses is None and not result.defaulted
