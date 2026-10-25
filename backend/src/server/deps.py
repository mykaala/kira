from functools import lru_cache

from agents.costlog import CostLog
from agents.llm import LLM, FakeLLM, OpenAILLM
from agents.runner import AgentRunner
from engine.engine import MODES

from .settings import get_settings


def make_llm() -> LLM:
    s = get_settings()
    if s.fake_llm:
        return FakeLLM()
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set: add it to backend/.env, or set FAKE_LLM=1 to play without it")
    return OpenAILLM(s.openai_api_key)


@lru_cache
def get_runner() -> AgentRunner:
    s = get_settings()
    for mode in MODES.values():  # a process-wide house rule
        mode.reveal_role_on_death = s.reveal_role_on_death
    return AgentRunner(make_llm(), s, CostLog(s.db_path))
