"""A fake model for the hidden-location game: random legal moves, read off the prompt, so the whole
stack runs with no key and no cost. Mafia's FakeLLM is left as it is."""

import asyncio
import json
import random

from engine.modes.spy_location import LOCATION_NAMES


class SpyFakeLLM:
    QUESTIONS = ["what do u usually wear here", "how long do people stay", "who do u come with", "is it loud"]
    ANSWERS = ["depends on the day", "mostly with friends lol", "pretty loud ngl", "a couple hours tops"]

    def __init__(self, seed: int = 0, delay_s: float = 0.0, leak_rate: float = 0.1, guess_rate: float = 0.3):
        self.rng = random.Random(seed)
        self.delay_s, self.leak_rate, self.guess_rate = delay_s, leak_rate, guess_rate

    def _legal(self, task: str, field: str) -> list[str]:
        key = f"Legal `{field}` values: "
        return json.loads(task.split(key)[1].split("\n")[0]) if key in task else []

    async def stream(self, *, model, messages, schema, max_tokens, reasoning_effort, usage):
        name, task = schema["name"], messages[-1]["content"]
        loc = task.split("THE LOCATION: ")[1].split(".")[0] if "THE LOCATION: " in task else None
        leak = f" kinda like a {loc}" if loc and self.rng.random() < self.leak_rate else ""
        if name == "ask":
            out = {"target": self.rng.choice(self._legal(task, "target")), "question": self.rng.choice(self.QUESTIONS)}
            out["question"] += leak
        elif name == "answer":
            out = {"text": self.rng.choice(self.ANSWERS) + leak}
        elif name == "vote":
            out = {"target": self.rng.choice(self._legal(task, "target"))}
        elif name == "spy_guess":
            legal = self._legal(task, "location") or LOCATION_NAMES
            last = "last chance" in task.lower() or "caught you" in task
            out = {"location": self.rng.choice(legal) if last or self.rng.random() < self.guess_rate else None}
        else:  # judge
            out = {"fits": self.rng.sample(LOCATION_NAMES, self.rng.randint(1, 12))}
        text = json.dumps(out)
        usage.input_tokens = sum(len(m["content"]) for m in messages) // 4
        usage.output_tokens = len(text) // 4
        for i in range(0, len(text), 16):
            if self.delay_s:
                await asyncio.sleep(self.delay_s)
            yield text[i : i + 16]
