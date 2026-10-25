from functools import lru_cache

from agents.costlog import CostLog
from agents.llm import LLM, FakeLLM, OpenAILLM
from agents.runner import AgentRunner
from agents.spy_fake import SpyFakeLLM
from agents.spy_runner import SpyRunner
from engine.engine import MODES

from .settings import BACKEND, get_settings


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


@lru_cache
def get_spy_runner() -> SpyRunner:
    """The Out of Place runner: free-text guesses ruled by the matcher, its memo in runs/ (fake runs apart)."""
    s = get_settings()
    llm = SpyFakeLLM(delay_s=0.01) if s.fake_llm else make_llm()
    memo = BACKEND / "runs" / ("spy_guess_memo-fake.json" if s.fake_llm else "spy_guess_memo.json")
    return SpyRunner(llm, s, CostLog(s.db_path), memo_path=memo)
