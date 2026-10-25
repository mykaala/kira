# Kira

Single-player social deduction against LLM AI players. Design and Mafia reference numbers: [docs/design.md](docs/design.md).
How to run everything: [documentation.md](documentation.md). UI source of truth: [design/UI_SPEC.md](design/UI_SPEC.md).

## Layout
- `backend/src/engine/`: pure game engine. No network, no OpenAI imports, no I/O. Seeded RNG via `state.rng(salt)`.
- `backend/src/agents/`: personas, prompts, output schemas, checks, the agent runner, the cost log.
- `backend/src/server/`: FastAPI + SSE, the per-game orchestrator, self-play, run summaries and metrics.
- `web/`: React 18 + TypeScript + Vite, CSS modules, Lantern Hour tokens in `web/src/styles/tokens.css`.

## Rules
- **Mafia is frozen** (v0.1-mafia): no behavior or balance changes. `tests/test_golden.py` must stay green.
- Model names live in `backend/src/server/settings.py` only. No new frameworks without asking.
- No player's view may contain another player's role or private/channel events (`tests/test_leak.py`).
- `backend/.env` holds the OpenAI key: never read, print or commit it. `.env.example` has placeholders only.
- Never shown during a game: a character's voice label (`voice`, e.g. "The Analyst"), or a dead player's role.
  One exception, Out of Place only: a player voted out is shown to have been a civilian (never a role at the place).
- Prompt = shared block (identical for every agent, over 1,100 tokens) + persona + dynamic view. One fixed JSON
  schema per call type listing the whole cast; legality is checked in code. Breaking either kills caching.
- Game names and text must be our own; reused mechanics need credit (Secret Hitler is CC BY-NC-SA 4.0).

## Commands (run from `backend/`)
- Install: `uv sync --python python3`. Python is pinned to 3.14.
- Tests: `uv run pytest` (about 30 s). Run after every change.
- Lint: `uvx --python .venv/bin/python ruff@0.7.4 check .` and `... format --check .`
- Self-play: `uv run python -m server.selfplay --games N [--parallel 4]` (about $0.016 a game). Output: `runs/`.
- Report: `uv run python scripts/report.py --run runs/<file>.jsonl`.
- API: `uv run uvicorn server.app:app --reload --timeout-graceful-shutdown 2`. Web: `cd web && npm run dev`.

## Pitfalls
- An old Python 2.7 is first on PATH: plain `uvx` fails, so pass `--python`.
- npm's cache is root-owned here: pass `--cache <scratch dir>` to npm.
- Closing the lid or sleeping the Mac kills self-play mid-run; lock the screen instead.
- `--reload` hangs on an open SSE stream without `--timeout-graceful-shutdown 2`.
- Players use nicknames ("marg", "toby"): name checks go through `checks.names()` / `NICKNAMES`.
