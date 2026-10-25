import json

import pytest

from engine.engine import MODES, IllegalMove, new_game, pending, submit_action, submit_say
from engine.views import build_view

MODE = MODES["mafia"]


def day_one():
    state = new_game(MODE, ["Ana", "Bo", "Cy", "Dee", "Eli", "Fay", "Gus"], None, 1)
    for r in pending(state):
        submit_action(state, r.pid, "abstain")
    assert state.phase == "discussion"
    return state


def say(state, accuses=None, text="hm"):
    pid = state.queue[0]
    submit_say(state, pid, text, accuses=accuses)
    return pid


def test_accusation_is_public_and_per_player():
    state = day_one()
    a = say(state, "p3")
    b = say(state, "p3")
    say(state, a)  # the next speaker points back
    for viewer in state.players:
        acc = build_view(MODE, state, viewer.id).accusations
        assert acc[a] == "p3" and acc[b] == "p3"


def test_latest_accusation_replaces_the_last_one_and_null_keeps_it():
    state = day_one()
    pid = state.queue[0]
    submit_say(state, pid, "kofi", accuses="p5" if pid != "p5" else "p4")
    state.queue.insert(0, pid)
    submit_say(state, pid, "no wait", accuses="p6" if pid != "p6" else "p4")
    state.queue.insert(0, pid)
    submit_say(state, pid, "still them")
    assert state.accusations[pid] == ("p6" if pid != "p6" else "p4")


def test_bad_accusations_are_rejected():
    state = day_one()
    pid = state.queue[0]
    with pytest.raises(IllegalMove, match="yourself"):
        submit_say(state, pid, "me?", accuses=pid)
    with pytest.raises(IllegalMove, match="living"):
        submit_say(state, pid, "ghost", accuses="nobody")


def test_cleared_after_the_vote_and_each_new_day():
    state = day_one()
    while state.phase == "discussion":
        pid = state.queue[0]
        target = next(p.id for p in state.alive() if p.id != pid)
        submit_say(state, pid, "you", accuses=target)
        if state.phase == "discussion":
            assert state.accusations
    assert state.phase == "vote" and state.accusations  # still showing while people vote
    for r in pending(state):
        submit_action(state, r.pid, "abstain")
    assert state.accusations == {}


def test_accuses_reaches_the_agent_runner_and_mismatch_is_logged(tmp_path):
    import asyncio

    from agents.costlog import CostLog
    from agents.personas import CAST
    from agents.runner import AgentRunner
    from agents.schemas import BeliefState
    from server.settings import Settings

    state = new_game(MODE, [p.name for p in CAST[:7]], None, 1)
    for r in pending(state):
        submit_action(state, r.pid, "abstain")
    view = build_view(MODE, state, state.queue[0])
    me = state.player(view.you).name
    other = next(p.name for p in view.players if p.name != me)
    third = next(p.name for p in view.players if p.name not in (me, other))

    class OneLLM:
        def __init__(self, reply):
            self.reply, self.schema = reply, None

        async def stream(self, *, usage, schema, **_):
            self.schema = schema
            yield self.reply

    async def run(accused, text):
        reply = json.dumps(
            {
                "say": text,
                "accuses": accused,
                "action": "none",
                "state": {"suspicion": [], "claims_heard": [], "my_claims": [], "plan": ""},
            }
        )
        settings = Settings(db_path=tmp_path / "t.db")
        llm = OneLLM(reply)
        runner = AgentRunner(llm, settings, CostLog(settings.db_path))
        result = await runner.play(
            game_id="g",
            view=view,
            persona=next(p for p in CAST if p.name == me),
            beliefs=BeliefState(),
            call_type="discussion",
            default_action="none",
        )
        # the enum is the whole cast, fixed for caching; who may be accused is checked in code
        assert llm.schema["schema"]["properties"]["accuses"]["anyOf"][0]["enum"] == [p.name for p in CAST]
        return result, runner.log.db.execute("SELECT accuse_mismatch FROM calls ORDER BY id DESC").fetchone()[0]

    result, mismatch = asyncio.run(run(other, f"{other.lower()} is lying"))
    assert result.accuses == next(p.id for p in view.players if p.name == other) and mismatch == 0
    result, mismatch = asyncio.run(run(other, f"{third.lower()} is lying"))
    assert mismatch == 1
