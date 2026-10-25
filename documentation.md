# Running Kira

This guide covers every way to run Kira: playing in the browser, playing without an API key, watching AI-only games, running the Milestone 1 gate, and running the tests. For what the game is and why it is built this way, see [design.md](docs/design.md).

## Quickest way to play

From the repo root, one command starts the backend and the web app and opens the browser (Mafia and Out of Place):

```
./start.sh          # real AI players (needs OPENAI_API_KEY in backend/.env)
./start.sh --fake   # free scripted AI players, no key needed
```

It installs anything missing on the first run and picks free ports (8000 and 5173 unless something else is using
them). Press Ctrl+C to stop everything it started.

## Contents

- [Quickest way to play](#quickest-way-to-play)
- [One-time setup](#one-time-setup)
- [Which mode do I want?](#which-mode-do-i-want)
- [Play in the browser](#play-in-the-browser)
- [The cast](#the-cast)
- [Play without an API key (fake mode)](#play-without-an-api-key-fake-mode)
- [Watch an all-AI game in the terminal](#watch-an-all-ai-game-in-the-terminal)
- [Run the Milestone 1 gate](#run-the-milestone-1-gate)
- [Run the tests](#run-the-tests)
- [Settings](#settings)
- [Troubleshooting](#troubleshooting)

## One-time setup

You need Python 3.14 (pinned in `backend/pyproject.toml`; deploy on the same version), [uv](https://docs.astral.sh/uv/), and Node 18 or newer.

```bash
# backend
cd backend
uv sync --python python3
cp .env.example .env          # then open backend/.env and paste your key after OPENAI_API_KEY=

# web client
cd ../web
npm install
```

`backend/.env` is gitignored, so your key is never committed. To check, run `git status --untracked-files=all | grep env`: only `.env.example` should appear. The key is used only by the backend and is never sent to the browser.

Set a monthly spending limit on your OpenAI account (Settings → Limits) before you share a link with anyone.

## Which mode do I want?

| I want to…                                         | Mode                                               | Uses the API? |
| -------------------------------------------------- | -------------------------------------------------- | ------------- |
| Play a game against AI players                     | [Play in the browser](#play-in-the-browser)        | Yes           |
| Work on the UI or engine without spending money    | [Fake mode](#play-without-an-api-key-fake-mode)    | No            |
| See how the AI players sound, quickly              | [Watch an all-AI game](#watch-an-all-ai-game-in-the-terminal) | Yes |
| Measure cost, latency and invalid moves            | [Milestone 1 gate](#run-the-milestone-1-gate)      | Yes           |
| Check nothing is broken after a change             | [Tests](#run-the-tests)                            | No            |

All backend commands below are run from the `backend/` folder, and all web commands from `web/`.

## Play in the browser

Open two terminals.

```bash
# terminal 1: the game server, on http://localhost:8000
cd backend
uv run uvicorn server.app:app --reload --timeout-graceful-shutdown 2
```

```bash
# terminal 2: the web client, on http://localhost:5173
cd web
npm run dev
```

Open http://localhost:5173. Pick **Mafia** and press **Light the lantern** (the other two games are coming soon). That opens the lobby, **"Who's at the table tonight?"**:

- **House rules** (always shown): your name, how many AI players (4 to 8), the roles, and how sharp the AIs are (**Cozy / Tricky / Merciless**).
  - Doctor and Detective are always in. **+ Jester** and **+ Bodyguard** each replace a villager.
- **Advanced settings** (closed by default): by default the table is **Auto**, a random cast, shown as **?** seats. Switch on **Choose who sits down** to pick the cast yourself:
  - Add people from the bench.
  - Tap a seat to see them **up close** and turn their three knobs (talkative, suspicious, good liar).
  - **Swap** or **Empty** a seat.
- **Blow out the lantern** deals the roles and starts the game.

Your lobby choices are remembered. **Characters** in the top bar shows the whole cast with their voices and knobs. If you have a game in progress, a strip on the game-select page offers to **pick up where you left off**.

**Optional roles**

| Role | Team | What it does |
|---|---|---|
| Jester | alone | Wins alone, and the game ends at once, if the town votes them out. Otherwise loses. To the detective, a jester is "not mafia". |
| Bodyguard | village | Each night guards one other player. If the mafia attack that player, the bodyguard dies instead. A doctor's save on the target beats both. |

**How sharp are they?** Difficulty shifts every AI's knobs and adds one line of strategy to their instructions:

| Difficulty | Suspicious | Good liar | Strategy |
|---|---|---|---|
| Cozy | −0.2 | −0.3 | Relaxed: they miss tells, trust a little too easily, and don't coordinate much. |
| Tricky | ±0 | ±0 | Each character's usual temperament. |
| Merciless | +0.15 | +0.25 | Plays to win: tracks every vote, punishes contradictions, bluffs carefully. |

Turning a character's knob by hand overrides the difficulty for that character (the lobby shows "custom knobs"); picking a difficulty again resets the knobs. The knobs reach the AI as plain words in its prompt ("you talk a lot; you are quick to accuse"), and talkative also sets how long its messages are.

**The screen**

- **Phase bar** (top): the day and phase, a candle that burns down as the discussion's turns are used up ("7 turns left"), **Auto**, **Pace** and **Call the vote**.
- **The table**: every living player as a chip. The speaker's chip lights up. Under each name is who that player is accusing right now (`→ Kit`). It comes from a public `accuses` field each message carries, not from guessing at the text, and it resets after each vote and at the start of each day. Eliminated players sit at the end as faded initials.
- **The stage**: the latest message, large: the speaker beside a speech bubble that types out. A "replying to" pill shows whom they're answering, and the people they named react underneath. The speaker's name tag shows only their name: their voice (the Analyst, the Hothead…) stays off the game screen, because it would hint at how they think. At night and during the vote, the stage becomes a tray of portraits to pick from.
- **The chat**: under the stage, one running, scrollable chat of the whole game, with day dividers. When the next message arrives, the one on stage joins the chat. It follows new messages while you're at the bottom; scroll up to read back and **↓ Latest** jumps down again. The ★ on a line pins it to your notes.
- **The action dock**: **Accuse / Defend / Ask / Claim role** each open a picker and draft a line you can edit before sending. **Accuse** also sets your public accusation, shown as a chip you can clear with ✕. Then type and press **Speak up**.
- **Notes** (right; under the dock on phones): always open, with your secret role card underneath.

**How a game goes**

1. **Night.** If you are mafia, the doctor or the detective, the stage shows portraits to pick your target (or **Skip tonight**). Villagers wait. Your result shows on your secret card and in the log, visible only to you.
2. **Morning.** The stage announces who died, if anyone. Nobody dies on night 1: the mafia only start killing on night 2.
3. **Discussion.** In round 1, every living player speaks exactly once, in a random order, and that includes you. When your turn comes, the dock lights up: say something or press **Pass**. If you do neither within 3 minutes, your turn is skipped. You can also speak at any other time; a message before your turn counts as your round-1 turn. Round 2 adds up to 3 extra AI speakers, picked first from the players who were accused or addressed. **Call the vote** skips the rest of the discussion.
4. **Vote.** Click a portrait to lock your vote, or **Abstain**. Everyone's ballots land one by one under the person they voted for.
5. This repeats until the village has removed every mafia member or the mafia equal everyone else.

**Pacing.** **Auto** is on by default: the AI players talk without waiting for you. Switch it off to step through the chat yourself: each AI message is then only generated when you press **Next** (or Enter in an empty message box), and the button names who speaks next. If you type something instead, the next speaker reacts to it. Your choice is remembered.

**Pace.** Messages type out at a readable speed, and votes, deaths and phase changes are revealed one at a time with a pause after each. **Pace** (Slow / Normal / Fast) changes both. It starts on **Slow** and your choice is remembered. Votes and night actions wait for you indefinitely.

**When a day ends.** A day is a fixed number of turns, not a time limit: in discussion round 1 every living player speaks once (you can pass), round 2 adds up to 3 extra AI speakers (those accused or named first), then the vote opens. The candle shows how many turns are left.

**Your reads.** Click any player's chip to record a read (**Trust / Unsure / Suspect / Mafia!**), a role guess (**Detective / Doctor / Villager**) and a short note. Your read shows as a coloured ring around their portrait, with the guess and note under their name. In the chat, the ★ on any line pins it to your **Notes**. Reads, pins and notes are saved in your browser for each game.

**Reloading.** The game id is kept in the address bar, so refreshing the page rejoins the same game with its chat history. If the backend was restarted in the meantime, the game is gone and the page offers a new one.

**After the game.** The results screen flips everyone's card face up (hover a card for their last words), with your reads marked on each. It names an MVP and the turning-point quote, and gives you stickers for what you did (saves, mafia found, good votes, surviving). **Replay the whole game** shows the full transcript; switch on **Show secrets** to also see every night action: the mafia's picks, the detective's results and the doctor's saves. **Rematch** starts a new game with the same settings.

**If you are eliminated,** you keep watching: the dock is replaced by a **Next** button while the chat waits.

## The cast

The same eight characters play every game. Each has a voice (the Analyst, the Hothead…) that shapes how they talk, whom they suspect and how they lie, a voice card of three sample lines, plus three trait knobs from 0 to 1. The voice is fixed per character (it is not dealt at random) and is shown in the lobby, on the Characters page and on the results screen, never during a game.

| Character | Voice | Talkative | Suspicious | Good liar | Plays like |
|---|---|---|---|---|---|
| Ines Varga | The Analyst | 0.5 | 0.6 | 0.4 | Precise and calm. Counts votes and points at who voted for whom. |
| Bram Holt | The Hothead | 0.9 | 0.8 | 0.25 | Loud and blunt. Accuses fast and distrusts quiet players. A bad liar. |
| Odile Fenn | The Quiet One | 0.2 | 0.7 | 0.6 | Few words. Notices contradictions and says them flatly. |
| Tobiah Reyes | The Charmer | 0.8 | 0.3 | 0.85 | Warm and smooth. Deflects with a smile. A natural liar. |
| Kit Amari | The Wildcard | 0.7 | 0.5 | 0.7 | Jokey and unpredictable. Swings between reads. |
| Marguerite Sol | The Elder | 0.4 | 0.4 | 0.3 | Calm and wry. Distrusts anyone who rushes the vote. |
| Juno Park | The Peacemaker | 0.6 | 0.2 | 0.3 | Tries to calm things down. Swayed by a heartfelt defence. |
| Hollis Wren | The Skeptic | 0.5 | 0.9 | 0.4 | Doubts every claim until it's proven. |

At the table, characters go by their first names, and your name can't be one of them. The personas live in [backend/src/agents/personas.py](backend/src/agents/personas.py); the portraits are drawn by [web/src/components/Portrait.tsx](web/src/components/Portrait.tsx). To see every character in every mood (neutral, angry, smug, speaking, dead), open http://localhost:5173/#/dev/portraits.

## Play without an API key (fake mode)

Fake mode swaps the model for scripted agents that make random legal moves and say short canned lines. It costs nothing and needs no key, so use it for UI work, engine changes, or demoing the flow.

```bash
cd backend
FAKE_LLM=1 uv run uvicorn server.app:app --reload --timeout-graceful-shutdown 2
```

Then start the web client as usual. Fake mode also works with self-play:

```bash
FAKE_LLM=1 uv run python -m server.selfplay --games 1
```

Fake games still write to the cost log, using estimated token counts. Point them at a separate database so they don't mix with real measurements:

```bash
FAKE_LLM=1 DB_PATH=fake.db uv run python -m server.selfplay --games 5
```

## Watch an all-AI game in the terminal

Self-play runs a game with no human. An extra AI character takes your seat.

```bash
cd backend
uv run python -m server.selfplay --games 1
```

It prints the whole game, including the secret parts: every player's role next to their name, the mafia's night choice, and detective results. Use it to judge whether the bluffs and accusations read well.

After each game it prints a summary:

- the winner, the number of days, and the number of players
- model calls, split by type (discussion, vote, night, summary)
- input, output and cached-input tokens, as reported by the API, and the dollar cost from the price table in settings
- p50 and p95 latency per call type
- first-try rejections (a first answer the code refused and retried) and invalid after retry (still unusable after the retry), retries, timeouts, reference-check flags, and turns that fell back to a default move

With `--games` above 1, an aggregate follows: the same figures over all games, plus the win rate for each side and the distribution of game lengths in days. Everything is also written to `backend/runs/<timestamp>.jsonl`: one line per game, including its full transcript, then one `"type": "aggregate"` line. The `runs/` folder is gitignored.

To read one game's transcript back from a run file:

```bash
python3 -c "import json,sys; g=json.loads(open(sys.argv[1]).readline()); print('\n'.join(g['transcript']))" backend/runs/<file>.jsonl
```

**Reference-check flags.** After each AI message, a best-effort check looks for statements credited to players who haven't spoken yet today, for example "Dara's claim" or "Toby, you said…". A flagged message is retried once with the instruction to use only what is in the transcript. If the retry is flagged too, it is posted anyway. Every flag is counted.

| Flag          | Default | Meaning                                                   |
| ------------- | ------- | --------------------------------------------------------- |
| `--games`     | 1       | How many games to play                                    |
| `--opponents` | 6       | AI players besides the human's seat (4 to 8)              |
| `--parallel`  | 1       | How many games to run at once                             |
| `--quiet`     | off     | Print only one result line per game (on automatically when `--games` is above 1) |

An all-Luna game measured about $0.03 on average across clean 7-player runs (the most expensive was about $0.08).

## Run the Milestone 1 gate

The gate is 20 complete games, measured against the targets in [design.md](docs/design.md#targets-and-playtest-rubric).

```bash
cd backend
uv run python -m server.selfplay --games 20 --parallel 4
uv run python scripts/report.py
```

The report reads the most recent 20 finished games from the cost log and marks each target as PASS or MISS:

| Metric                              | Target    |
| ----------------------------------- | --------- |
| Time to first streamed token (p95)  | < 2 s     |
| Vote or night round, all AI in (p95) | < 4 s    |
| Invalid after retry                 | < 1%      |
| Game length (average)               | 8–12 min  |
| Cost per game (average and maximum) | ≤ $0.15   |

It also prints calls per game, token totals (including cached tokens), and the most common errors.

Notes:

- `--parallel 4` makes the run faster, but games then compete for API capacity, which can inflate latency. For the cleanest latency numbers, run with `--parallel 1`.
- Self-play has no pauses between speakers, so game length here is shorter than a game you play yourself. Measure game length from your own browser games too.
- `report.py --last N` reports on the last N games instead of 20. `report.py --db path` reads a different database.
- `report.py --run runs/<file>.jsonl` reports on exactly the games in one self-play run, and adds the balance and voice metrics (night-1 check vs. wins, detective claims and counterclaims, when the first mafia was caught, kills blocked by the doctor, mafia voting together, stock-phrase use, distinct bigrams) and every reference-check flag with its reason. Older runs are re-scored from their saved transcripts.
- Keep a laptop plugged in with the lid open for the whole run. Closing the lid puts the Mac to sleep even under `caffeinate`, and the API becomes unreachable. If that happens, an AI turn retries for about a minute, then the run stops and leaves the broken game out of the summary rather than finishing it with random moves.
- To keep the Mac awake while the lid is open, prefix the command with `caffeinate -is` and call the project's Python directly, because `uv run` under `caffeinate` trips over the old Python 2.7 on the PATH: `caffeinate -is .venv/bin/python -m server.selfplay --games 20`.

**Reading the raw log.** Every model call is stored in `backend/kira.db`, with tokens, dollars, latency, and the full prompt and response, so you can replay any turn:

```bash
sqlite3 backend/kira.db "SELECT player, call_type, model, cost_usd, latency_ms, error FROM calls ORDER BY id DESC LIMIT 20"
```

The tables are `games` (one row per game, with every player's role), `calls` (one row per model call attempt) and `rounds` (latency of each parallel vote or night round).

## Run the tests

```bash
cd backend
uv run pytest
uvx --python .venv/bin/python ruff@0.7.4 check .
uvx --python .venv/bin/python ruff@0.7.4 format --check .
cd ../web && npx tsc --noEmit -p . && npx vite build
```

(`--python` points uv at the project's Python 3.14, because an old Python 2.7 is first on this machine's PATH.) The tests use no API and finish in about 30 seconds. They cover:

- **Golden games:** three seeded all-AI Mafia games with the fake model, saved in full in `backend/tests/golden/`, must replay byte-for-byte. Mafia is frozen; if a change to it is intended, regenerate with `UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py` and review the diff.
- **Claims, accusations and roles hidden on death:** detective claims judged against real results, fake claims logged as false, accusations validated and cleared, dead roles hidden until the end.
- **Prompt layout:** the shared block is identical for every agent and long enough to cache, every agent gets the same schema per call type, and illegal picks are retried then defaulted.

- **Leak test:** across 200 seeded games, no player's view ever contains a role or private message their role may not know.
- **Random games:** 1,000 games played by random bots all finish with a winner, and the same seed always produces the same game.
- **Resolvers:** the doctor's save, detective results, tied votes, plurality votes and both win conditions, and that the mafia can never target a teammate at night.
- **Discussion:** across 200 games, every living player speaks in every day's discussion, and nobody speaks twice before everyone has spoken once.
- **First night:** across 200 games, nobody dies on night 1, while the detective and doctor still act; the morning announcement is the first public line of each day.
- **Reference check:** hand-written and planted messages (including nicknames and short names such as "marg" and "toby") that should and shouldn't be flagged.
- **Optional roles:** the bodyguard dies in place of the guarded player, a doctor's save beats both, a voted-out jester wins alone, and 300 random games with both roles finish without leaks (each side, including the jester, wins some).
- **Game setup API:** a chosen cast, hand-set knobs, difficulty and optional roles all reach the game; bad casts are rejected. These run against a fake model and a throwaway database.
- **Agent runner:** streaming text extraction, a retry after an illegal move, falling back to a default after two failures, timeouts, rejecting messages that break character, texting-style cleanup and the 25-word cap, trimming private notes so prompts stay bounded, riding out a brief connection drop, and stopping (not defaulting) when the API stays unreachable.

## Settings

Every setting can go in `backend/.env` or be set as an environment variable for one command (for example `MODEL_DISCUSSION=gpt-5.6-terra uv run …`). Names are not case-sensitive.

| Setting                    | Default        | What it does                                                        |
| -------------------------- | -------------- | ------------------------------------------------------------------- |
| `OPENAI_API_KEY`           | none           | Your OpenAI key. Required unless `FAKE_LLM=1`.                      |
| `FAKE_LLM`                 | `0`            | `1` uses scripted random agents and makes no API calls.             |
| `MODEL_DISCUSSION`         | `gpt-5.6-luna` | Model for discussion messages.                                      |
| `MODEL_VOTE`               | `gpt-5.6-luna` | Model for day votes.                                                |
| `MODEL_NIGHT`              | `gpt-5.6-luna` | Model for night actions.                                            |
| `REASONING_EFFORT`         | `low`          | Reasoning effort sent with every call. Higher is slower and costs more. |
| `MODEL_MAFIA_DISCUSSION`   | (off)          | Override model for discussion messages by mafia players only, e.g. `gpt-5.6-terra`. |
| `MODEL_MAFIA_NIGHT`        | (off)          | Override model for the mafia's night kill only.                     |
| `OVERRIDE_REASONING_EFFORT` | `low`         | Reasoning effort for calls that use an override model.              |
| `CALL_TIMEOUT_S`           | `10`           | Deadline per model call, in seconds. A timed-out call is retried once, then a safe default move is used. |
| `CONNECT_BACKOFF_S`        | `[2,5,10,20,30]` | Waits, in seconds, before each reconnect when the API is unreachable. After the last one the game stops. |
| `MAX_OUTPUT_TOKENS`        | `1500`         | Output cap per discussion call, including reasoning tokens. Too low and replies get cut off mid-JSON. |
| `MAX_OUTPUT_TOKENS_ACTION` | `400`          | Output cap per vote or night call. These answer `{"action": ...}` only. |
| `PHRASE_CAP`               | `2`            | Uses per game, across the whole table, of each stock phrase (convenient, staged, pile-on/dogpile, leap, proves nothing, lazy, reeks, too neat, tidy). Once a phrase is spent, prompts ban it; a message that uses it anyway is retried once. |
| `REVEAL_ROLE_ON_DEATH`     | `false`        | Roles stay hidden when a player dies and are shown only at the end (results and review). `true` announces each dead player's role. |
| `GAME_TOKEN_BUDGET`        | `400000`       | Hard token limit per game. Past it, AI players use default moves until the game ends. |
| `DB_PATH`                  | `backend/kira.db` | Where the cost log is written.                                |
| `MAX_GAMES_PER_IP_PER_HOUR` | `20`          | How many games one visitor can start per hour.                      |
| `DISCUSSION_PAUSE_S`       | `1.2`          | Pause between AI speakers in browser games on **Auto**. On-screen pacing (typing speed, pauses after votes and deaths) is set by **Pace** in the browser. |
| `HUMAN_TURN_TIMEOUT_S`     | `180`          | How long the game waits for you on your discussion turn before skipping it. |

**Upgrading a call type to Terra.** The design doc's plan is to try GPT-5.6 Terra for discussion if Luna's bluffing reads as weak. Only that call type changes:

```bash
# in backend/.env
MODEL_DISCUSSION=gpt-5.6-terra
```

Terra for all discussion costs about $0.25 a game, according to the design doc's estimate. Prices are kept in `prices` in [backend/src/server/settings.py](backend/src/server/settings.py); recheck them against OpenAI's pricing page before relying on the report's dollar figures.

## Troubleshooting

**`OPENAI_API_KEY is not set`**
The backend found no key. Check that `backend/.env` exists, contains `OPENAI_API_KEY=sk-…` with no quotes or spaces around `=`, and is saved. Or run with `FAKE_LLM=1`.

**`uv sync` fails with `Bad CPU type in executable` or mentions Python 2.7**
An old Python 2.7 is first on your PATH. Run `uv sync --python python3`. The project pins Python 3.14 in `backend/.python-version`.

**`npm install` fails with a permissions error about `~/.npm`**
Your npm cache is owned by root. Fix it once with `sudo chown -R $(id -u):$(id -g) ~/.npm`, or install with a separate cache: `npm install --cache /tmp/npm-cache`.

**The page says "Connecting…" forever, or Start does nothing**
The backend isn't running, or is on another port. Start it with `uvicorn` on port 8000; the web client forwards `/api` requests there.

**Start is stuck on "Dealing roles…"**
The backend is frozen mid-restart. With `--reload`, uvicorn restarts whenever a backend file changes, but first it waits for open connections to close, and a game tab's live chat stream never closes on its own. Stop the server with Ctrl+C (press it twice if needed) and start it again with the command above: `--timeout-graceful-shutdown 2` makes it give up waiting after 2 seconds. Running games are lost on a restart, so start a new one.

**`too many games this hour`**
The per-visitor limit was hit. Raise `MAX_GAMES_PER_IP_PER_HOUR` in `.env` for local testing.

**"Lost the connection to the AI service"**
The backend couldn't reach OpenAI for about a minute, so the game stopped instead of continuing with random moves. Check your internet connection (and that the Mac didn't sleep), then start a new game.

**AI players go quiet, or every vote is an abstain**
Their calls are probably failing and falling back to defaults. Check the `error` column of the cost log:

```bash
sqlite3 backend/kira.db "SELECT error, COUNT(*) FROM calls WHERE error IS NOT NULL GROUP BY error"
```

Timeouts mean `CALL_TIMEOUT_S` is too short for the current model or reasoning effort. Authentication or quota errors point to the key or the account's spending limit.
