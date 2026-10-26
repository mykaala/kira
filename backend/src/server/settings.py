from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND / ".env", extra="ignore")

    openai_api_key: str = ""
    fake_llm: bool = False  # play with scripted random agents, no API calls

    # model per call type: upgrading one never touches game code
    model_discussion: str = "gpt-5.6-luna"
    model_vote: str = "gpt-5.6-luna"
    model_night: str = "gpt-5.6-luna"
    # hidden-location game (spy_location); its votes use model_vote
    model_ask: str = "gpt-5.6-luna"
    model_answer: str = "gpt-5.6-luna"
    model_spy_guess: str = "gpt-5.6-luna"
    model_last_chance: str = "gpt-5.6-luna"
    model_judge: str = "gpt-5.6-luna"  # offline specificity judge, self-play harness only
    model_guess_judge: str = "gpt-5.6-luna"  # does a free-text spy guess name the secret location
    model_roles: str = "gpt-5.6-terra"  # offline role-bank generator only (scripts/spy_roles_gen.py), never in a game
    model_role_audit: str = "gpt-5.6-luna"  # offline: which places each role title fits (scripts/spy_roles_audit.py)
    model_role_judge: str = "gpt-5.6-luna"  # offline: does a civilian's answer fit its own role and the place
    reasoning_effort: str = "low"
    # per-role overrides, off when empty: e.g. MODEL_MAFIA_DISCUSSION=gpt-5.6-terra
    model_mafia_discussion: str = ""
    model_mafia_night: str = ""
    override_reasoning_effort: str = "low"  # used for calls that take an override model

    call_timeout_s: float = 10.0
    connect_backoff_s: list[float] = [2, 5, 10, 20, 30]  # waits before giving up on an unreachable API
    max_output_tokens: int = 1500  # discussion; includes reasoning tokens; 600 cut replies off mid-JSON
    max_output_tokens_action: int = 400  # votes and night moves answer {"action": ...} only
    max_output_tokens_guess: int = 800  # spy guesses, last chances and the guess judge; 400 came back empty
    phrase_cap: int = 2  # uses per game, across the table, of each capped stock phrase
    reveal_role_on_death: bool = (
        False  # roles stay hidden until the game ends (results and review); true reveals on death
    )
    game_token_budget: int = 400_000  # input + output; past this, moves fall back to defaults

    # $ per million tokens: input, output, cached input (recheck OpenAI's pricing page)
    prices: dict[str, tuple[float, float, float]] = {
        "gpt-5.6-luna": (0.20, 1.20, 0.02),
        "gpt-5.6-terra": (2.00, 12.00, 0.20),
    }

    db_path: Path = BACKEND / "kira.db"
    max_games_per_ip_per_hour: int = 20
    discussion_pause_s: float = 1.2  # beat between AI speakers so the human can read and interject
    human_turn_timeout_s: float = 180.0  # the human's discussion turn is skipped after this
    spy_idle_timeout_s: float = 1800.0  # Out of Place: a game waiting this long on the person ends

    def model_for(self, call_type: str, role: str | None = None) -> str:
        return self.override_for(call_type, role) or getattr(self, f"model_{call_type}")

    def override_for(self, call_type: str, role: str | None) -> str:
        """The per-role override model for this call, or "" if none is set."""
        return getattr(self, f"model_{role}_{call_type}", "") if role else ""

    def effort_for(self, call_type: str, role: str | None = None) -> str:
        return self.override_reasoning_effort if self.override_for(call_type, role) else self.reasoning_effort

    def overrides(self) -> dict[str, str]:
        return {
            k.removeprefix("model_"): v
            for k, v in (
                ("model_mafia_discussion", self.model_mafia_discussion),
                ("model_mafia_night", self.model_mafia_night),
            )
            if v
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
