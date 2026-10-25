"""What an agent returns. `say` comes first so it streams first."""

from pydantic import BaseModel, Field


class Suspicion(BaseModel):
    player: str
    score: int  # 0 trust .. 10 sure they are an enemy


NOTE_ITEMS = 6  # notes are fed back every turn, so they must not grow without bound
NOTE_CHARS = 100


class BeliefState(BaseModel):
    suspicion: list[Suspicion] = Field(default_factory=list)
    claims_heard: list[str] = Field(default_factory=list)
    my_claims: list[str] = Field(default_factory=list)  # what I have said publicly, so I stay consistent
    plan: str = ""

    def trimmed(self) -> "BeliefState":
        """The most recent few notes, each kept short."""
        short = lambda items: [s[:NOTE_CHARS] for s in items[-NOTE_ITEMS:]]  # noqa: E731
        return BeliefState(
            suspicion=self.suspicion[:12],
            claims_heard=short(self.claims_heard),
            my_claims=short(self.my_claims),
            plan=self.plan[: NOTE_CHARS * 2],
        )


class ClaimOut(BaseModel):
    role: str
    target: str | None = None  # a player name
    result: str | None = None


class AgentMove(BaseModel):
    """A discussion turn fills say/accuses/claim/state; a vote or night turn only `action`."""

    say: str = ""
    accuses: str | None = None  # a player name, public
    claim: ClaimOut | None = None
    action: str = "none"
    state: BeliefState = Field(default_factory=BeliefState)


CLAIM_RESULTS = ["mafia", "not mafia"]


def claim_schema(roles: list[str], names: list[str]) -> dict:
    """An optional public role claim: null, or {role, target, result}."""
    nullable = lambda enum: {"anyOf": [{"type": "string", "enum": enum}, {"type": "null"}]}  # noqa: E731
    return {
        "anyOf": [
            {"type": "null"},
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["role", "target", "result"],
                "properties": {
                    "role": {"type": "string", "enum": roles},
                    "target": nullable(names),
                    "result": nullable(CLAIM_RESULTS),
                },
            },
        ]
    }


def accuse_schema(names: list[str]) -> dict:
    """Who the message points at as a suspect: one living player, or null."""
    return {"anyOf": [{"type": "string", "enum": names}, {"type": "null"}]}


STATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["suspicion", "claims_heard", "my_claims", "plan"],
    "properties": {
        "suspicion": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["player", "score"],
                "properties": {"player": {"type": "string"}, "score": {"type": "integer"}},
            },
        },
        "claims_heard": {"type": "array", "items": {"type": "string"}},
        "my_claims": {"type": "array", "items": {"type": "string"}},
        "plan": {"type": "string"},
    },
}


def _strict(name: str, properties: dict) -> dict:
    return {
        "name": name,
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        },
    }


def discussion_schema(accuses: dict | None = None, claim: dict | None = None) -> dict:
    """`say` first so it streams first; then the public accusation and claim; then private notes."""
    props = {"say": {"type": "string"}}
    props |= {k: v for k, v in (("accuses", accuses), ("claim", claim)) if v}
    return _strict("discussion", props | {"state": STATE_SCHEMA})


def action_schema(action_choices: list[str]) -> dict:
    """A vote or night move: only the action, so the answer is a handful of tokens."""
    return _strict("action", {"action": {"type": "string", "enum": action_choices}})
