"""Model clients. `OpenAILLM` is the real one; `FakeLLM` plays random legal moves so the
whole stack can run with no key and no cost."""

import asyncio
import json
import random
from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel


class Usage(BaseModel):
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0  # part of output_tokens


class LLM(Protocol):
    def stream(
        self, *, model: str, messages: list[dict], schema: dict, max_tokens: int, reasoning_effort: str, usage: Usage
    ) -> AsyncIterator[str]: ...


class OpenAILLM:
    def __init__(self, api_key: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, max_retries=0)

    async def stream(self, *, model, messages, schema, max_tokens, reasoning_effort, usage):
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_schema", "json_schema": schema},
            max_completion_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if chunk.usage:
                usage.input_tokens = chunk.usage.prompt_tokens
                usage.output_tokens = chunk.usage.completion_tokens
                details = chunk.usage.prompt_tokens_details
                usage.cached_tokens = (details.cached_tokens or 0) if details else 0
                out = chunk.usage.completion_tokens_details
                usage.reasoning_tokens = (out.reasoning_tokens or 0) if out else 0
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class FakeLLM:
    LINES = [
        "{t} has been way too quiet.",
        "I don't trust {t}, honestly.",
        "Why did {t} change their story?",
        "I'm fine with {t} for now.",
        "Something about {t} feels off.",
    ]

    def __init__(self, seed: int = 0, delay_s: float = 0.02):
        self.rng = random.Random(seed)
        self.delay_s = delay_s

    async def stream(self, *, model, messages, schema, max_tokens, reasoning_effort, usage):
        props = schema["schema"]["properties"]
        players = next(m["content"] for m in messages if "PLAYERS AT THE TABLE: " in m["content"])
        players = players.split("PLAYERS AT THE TABLE: ")[1].split("\n")[0].split(", ")
        task = messages[-1]["content"]
        if "action" in props:  # the schema lists every name; pick one the prompt says is legal
            legal = json.loads(task.split("Legal `action` values: ")[1].split("\n")[0])
            out = {"action": self.rng.choice(legal)}
        else:
            out = {"say": self.rng.choice(self.LINES).format(t=self.rng.choice(players))}
            out |= {k: None for k in ("accuses", "claim") if k in props}
            alive = task.split("Alive (besides you): ")[1].split(".\n")[0].split(", ")
            if "accuses" in props and self.rng.random() < 0.6:
                out["accuses"] = self.rng.choice(alive)
            out["state"] = {"suspicion": [], "claims_heard": [], "my_claims": [], "plan": "watch"}
        text = json.dumps(out)
        usage.input_tokens = sum(len(m["content"]) for m in messages) // 4
        usage.output_tokens = len(text) // 4
        for i in range(0, len(text), 12):
            await asyncio.sleep(self.delay_s)
            yield text[i : i + 12]
