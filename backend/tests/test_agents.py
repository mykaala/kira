import asyncio
import json

from agents.costlog import CostLog
from agents.personas import CAST
from agents.runner import AgentRunner, SayExtractor
from agents.schemas import BeliefState
from engine.engine import MODES, new_game
from engine.views import build_view
from server.settings import Settings

STATE = {"suspicion": [], "claims_heard": [], "my_claims": [], "plan": ""}


def test_say_extractor_streams_across_chunks_and_escapes():
    text = json.dumps({"say": 'Mei said "trust me" — no.\nReally', "action": "none", "state": STATE})
    ex = SayExtractor()
    out = "".join(ex.feed(text[i : i + 3]) for i in range(0, len(text), 3))
    assert out == 'Mei said "trust me" — no.\nReally'


class ScriptedLLM:
    def __init__(self, replies, delay=0.0):
        self.replies, self.delay, self.calls = list(replies), delay, 0

    async def stream(self, *, usage, **_):
        self.calls += 1
        await asyncio.sleep(self.delay)
        usage.input_tokens, usage.output_tokens = 1000, 50
        yield self.replies.pop(0)


def setup(llm, tmp_path, **kw):
    settings = Settings(db_path=tmp_path / "t.db", **kw)
    state = new_game(MODES["mafia"], [p.name for p in CAST[:7]], None, 1)
    state.phase = "vote"
    view = build_view(MODES["mafia"], state, "p0")
    return AgentRunner(llm, settings, CostLog(settings.db_path)), view


async def play(runner, view, call_type="vote"):
    return await runner.play(
        game_id="g", view=view, persona=CAST[0], beliefs=BeliefState(), call_type=call_type, default_action="abstain"
    )


async def test_illegal_action_retries_then_succeeds(tmp_path):
    good = json.dumps({"say": "", "action": CAST[1].name, "state": STATE})
    bad = json.dumps({"say": "", "action": "Nobody", "state": STATE})
    llm = ScriptedLLM([bad, good])
    runner, view = setup(llm, tmp_path)
    result = await play(runner, view)
    assert llm.calls == 2 and result.action == "p1" and not result.defaulted


async def test_two_failures_fall_back_to_default(tmp_path):
    llm = ScriptedLLM(["not json", "{}"])
    runner, view = setup(llm, tmp_path)
    result = await play(runner, view)
    assert result.defaulted and result.action == "abstain"


async def test_timeout_falls_back(tmp_path):
    llm = ScriptedLLM(["x", "x"], delay=0.2)
    runner, view = setup(llm, tmp_path, call_timeout_s=0.05)
    result = await play(runner, view)
    assert result.defaulted
    rows = runner.log.db.execute("SELECT error FROM calls").fetchall()
    assert all("timed out" in r[0] for r in rows)


async def test_breaking_character_is_rejected(tmp_path):
    bad = json.dumps({"say": "As an AI, I cannot lie.", "action": "none", "state": STATE})
    good = json.dumps({"say": "Ines is sus.", "action": "none", "state": STATE})
    runner, view = setup(ScriptedLLM([bad, good]), tmp_path)
    view.legal_actions = []
    result = await play(runner, view, call_type="discussion")
    assert result.say == "ines is sus"


async def test_reference_flag_retries_once_with_instruction(tmp_path):
    invented = json.dumps({"say": "Odile's claim is nonsense.", "action": "none", "state": STATE})
    fixed = json.dumps({"say": "Nobody's said much yet. Odile, start us off.", "action": "none", "state": STATE})
    llm = ScriptedLLM([invented, fixed])
    runner, view = setup(llm, tmp_path)
    view.legal_actions, view.phase = [], "discussion"
    result = await play(runner, view, call_type="discussion")
    assert result.say.startswith("nobody's said much")
    rows = runner.log.db.execute("SELECT ref_flag, valid, error, prompt FROM calls ORDER BY id").fetchall()
    assert [r[0] for r in rows] == [1, 0] and rows[0][2].startswith("You referred to a statement")
    assert "You referred to a statement that was not made" in rows[1][3]


async def test_second_reference_flag_is_posted_and_counted(tmp_path):
    invented = json.dumps({"say": "Odile's claim is nonsense.", "action": "none", "state": STATE})
    runner, view = setup(ScriptedLLM([invented, invented]), tmp_path)
    view.legal_actions, view.phase = [], "discussion"
    result = await play(runner, view, call_type="discussion")
    assert result.say == "odile's claim is nonsense" and not result.defaulted
    assert runner.log.db.execute("SELECT SUM(ref_flag) FROM calls").fetchone()[0] == 2


def test_texting_style_lowercases_but_keeps_yelling():
    from agents.checks import check_say

    say, err = check_say("Okay — Mei is LYING; I KNOW it. Vote Mei.")
    assert err is None and say == "okay, mei is LYING, i KNOW it. vote mei"


def test_long_messages_are_capped():
    from agents.checks import MAX_WORDS, check_say

    say, _ = check_say(" ".join(["word"] * 80))
    assert len(say.split()) == MAX_WORDS


def test_beliefs_are_trimmed_so_prompts_stay_bounded():
    from agents.schemas import NOTE_CHARS, NOTE_ITEMS

    b = BeliefState(claims_heard=[f"claim {i} " + "x" * 300 for i in range(30)], my_claims=["a"] * 30)
    t = b.trimmed()
    assert len(t.claims_heard) == NOTE_ITEMS and t.claims_heard[-1].startswith("claim 29")
    assert all(len(c) <= NOTE_CHARS for c in t.claims_heard) and len(t.my_claims) == NOTE_ITEMS


class DownLLM:
    def __init__(self):
        self.calls = 0

    async def stream(self, **_):
        self.calls += 1
        raise ConnectionError("network is down")
        yield  # pragma: no cover


async def test_unreachable_api_waits_then_stops_instead_of_defaulting(tmp_path):
    import pytest
    from agents.runner import ModelUnavailable

    llm = DownLLM()
    runner, view = setup(llm, tmp_path, connect_backoff_s=[0, 0, 0])
    with pytest.raises(ModelUnavailable):
        await play(runner, view)
    assert llm.calls == 4  # first try plus three reconnects, then give up


async def test_connection_recovers_after_a_blip(tmp_path):
    class BlipLLM(ScriptedLLM):
        async def stream(self, *, usage, **kw):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("blip")
            usage.input_tokens, usage.output_tokens = 1000, 50
            yield self.replies.pop(0)

    good = json.dumps({"say": "", "action": CAST[1].name, "state": STATE})
    runner, view = setup(BlipLLM([good]), tmp_path, connect_backoff_s=[0])
    result = await play(runner, view)
    assert result.action == "p1" and not result.defaulted


class SchemaLLM(ScriptedLLM):
    """Remembers whether each call's schema allowed a claim."""

    def __init__(self, replies):
        super().__init__(replies)
        self.claim_allowed = []

    async def stream(self, *, usage, schema, **kw):
        self.claim_allowed.append("claim" in schema["schema"]["properties"])
        async for chunk in super().stream(usage=usage, **kw):
            yield chunk


def say_with_claim(text, claim):
    return json.dumps({"say": text, "claim": claim, "action": "none", "state": STATE})


async def test_rejected_claim_retries_then_regenerates_without_claim(tmp_path):
    bad = say_with_claim(
        "im detective, bram is mafia", {"role": "detective", "target": CAST[1].name, "result": "mafia"}
    )
    plain = say_with_claim("bram is acting weird", None)
    llm = SchemaLLM([bad, bad, plain])
    runner, view = setup(llm, tmp_path)
    view.legal_actions, view.phase = [], "discussion"
    seen = []
    result = await runner.play(
        game_id="g",
        view=view,
        persona=CAST[0],
        beliefs=BeliefState(),
        call_type="discussion",
        default_action="none",
        claim_roles=["detective"],
        judge_claim=lambda c: seen.append(c) or "you never checked Bram",
    )
    assert llm.claim_allowed == [True, True, False]
    assert result.say == "bram is acting weird" and result.claim is None
    assert seen[0].target == "p1" and seen[0].result == "mafia"  # names are mapped back to ids
    errors = [r[0] for r in runner.log.db.execute("SELECT error FROM calls ORDER BY id")]
    assert "you never checked Bram" in errors[0] and errors[2] is None


async def test_accepted_claim_is_returned(tmp_path):
    ok = say_with_claim("im the doctor fyi", {"role": "doctor", "target": None, "result": None})
    runner, view = setup(SchemaLLM([ok]), tmp_path)
    view.legal_actions, view.phase = [], "discussion"
    result = await runner.play(
        game_id="g",
        view=view,
        persona=CAST[0],
        beliefs=BeliefState(),
        call_type="discussion",
        default_action="none",
        claim_roles=["doctor"],
        judge_claim=lambda c: None,
    )
    assert result.claim.role == "doctor" and result.claim.target is None


class ModelLLM(ScriptedLLM):
    def __init__(self, replies):
        super().__init__(replies)
        self.seen = []

    async def stream(self, *, usage, model, reasoning_effort, **kw):
        self.seen.append((model, reasoning_effort))
        async for chunk in super().stream(usage=usage, **kw):
            yield chunk


async def test_mafia_discussion_override_uses_its_own_model_and_effort(tmp_path):
    reply = json.dumps({"say": "hm", "action": "none", "state": STATE})
    llm = ModelLLM([reply, reply])
    runner, view = setup(
        llm,
        tmp_path,
        model_mafia_discussion="gpt-5.6-terra",
        reasoning_effort="medium",
        override_reasoning_effort="low",
    )
    view.legal_actions, view.phase = [], "discussion"
    view.role = "mafia"
    await play(runner, view, call_type="discussion")
    view.role = "villager"
    await play(runner, view, call_type="discussion")
    assert llm.seen == [("gpt-5.6-terra", "low"), ("gpt-5.6-luna", "medium")]
    models = [r[0] for r in runner.log.db.execute("SELECT model FROM calls ORDER BY id")]
    assert models == ["gpt-5.6-terra", "gpt-5.6-luna"]


def test_overrides_are_off_by_default():
    s = Settings(_env_file=None)
    assert s.overrides() == {} and s.model_for("discussion", "mafia") == s.model_discussion
    assert s.model_for("night", "mafia") == s.model_night
