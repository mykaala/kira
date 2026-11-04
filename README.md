<p align="center">
  <img src="design/kira_banner.png" alt="Kira — Three games of trust and betrayal" width="100%">
</p>

**Pick a game: Mafia or Out of Place, with Trojan Horse on the way. Every other seat at the table is an AI player with its own character, its own voice, and something to hide.**

> 🚧 **Status:** Mafia and Out of Place are playable in the browser and were balanced in self-play (stats below). Trojan Horse is next. Not deployed yet, so you run it on your own machine.

## 📚 Table of contents

0. [Run it](#run)
1. [Mafia](#mafia)
   - 1a. [How a round goes](#mafia-rules)
   - 1b. [How it differs from the real game](#mafia-differs)
   - 1c. [Balancing the agents](#mafia-balance)
2. [Out of Place](#spy)
   - 2a. [How a round goes](#spy-rules)
   - 2b. [How it differs from the original](#spy-differs)
   - 2c. [Balancing the agents](#spy-balance)
3. [Trojan Horse (coming soon)](#th)
4. [How the AIs work](#ai)
   - 4a. [The model and the API](#ai-model)
   - 4b. [Prompt layering](#ai-prompt)
   - 4c. [Structured moves](#ai-moves)
   - 4d. [Code rolls the dice](#ai-dice)
   - 4e. [Settings and logging](#ai-settings)
5. [What's next](#next)
6. [Credits and license](#credits)

---

<a id="run"></a>

## ▶️ 0. Run it

You need Python 3.14, [uv](https://docs.astral.sh/uv/) and Node 18 or newer. The AI players use the OpenAI API, so a real game needs an OpenAI key. Fake mode needs no key and costs nothing: the AIs are scripted.

**One command** (macOS or Linux, from the repo root). It installs what's missing, starts the backend and the web app, and opens the browser:

```bash
./start.sh --fake   # scripted AI players, no key needed
./start.sh          # real AI players (needs your key in backend/.env, see below)
```

**Or by hand, in two terminals:**

```bash
# terminal 1: the game server, on http://localhost:8000
cd backend
uv sync                       # if uv picks the wrong Python: uv sync --python python3.14
cp .env.example .env          # then paste your key after OPENAI_API_KEY=
uv run uvicorn server.app:app --timeout-graceful-shutdown 2
# no key? start it with FAKE_LLM=1 in front instead:
# FAKE_LLM=1 uv run uvicorn server.app:app --timeout-graceful-shutdown 2
```

```bash
# terminal 2: the web app, on http://localhost:5173
cd web
npm install
npm run dev
```

Then open http://localhost:5173. `backend/.env` is gitignored, and the key is only ever read by the server. Before you share a link with anyone, set a monthly spending limit on your OpenAI account.

**Tests:** `cd backend && uv run pytest` (about a minute, no key needed). Everything else (all-AI games in the terminal, self-play runs, settings, troubleshooting) is in [documentation.md](documentation.md).

---

<a id="mafia"></a>

## 🎲 1. Mafia

You and 4 to 8 AI players. One or two of them are mafia and lying to everyone else. Figure out who before the village runs out of people.

<a id="mafia-rules"></a>

### 1a. How a round goes

**Night** (kill, save, check) → **Morning** (who died?) → **Chat** (accuse, defend, claim a role) → **Vote** someone out → repeat.

The village wins when the mafia are gone. The mafia win when they equal or outnumber everyone else.

| Role                   | How many                         | What they do                                                                 |
| ---------------------- | -------------------------------- | ---------------------------------------------------------------------------- |
| 🦹 Mafia               | 1 (up to 6 players), 2 (7 to 9)  | Know each other. Pick one player to kill each night                           |
| 🕵️ Detective           | 1                                | Checks one player a night: mafia or not                                      |
| 👩‍⚕️ Doctor              | 1                                | Protects one player a night, never the same one two nights in a row          |
| 🧑‍🌾 Villager            | the rest                         | Talk, think, vote                                                            |
| 🃏 Jester (optional)   | replaces a villager              | Wins alone, at once, if the town votes them out                              |
| 🛡️ Bodyguard (optional) | replaces a villager              | Guards one other player a night, and dies in their place if the mafia attack |

<a id="mafia-differs"></a>

### 1b. How it differs from the real game

- **No host or moderator.** Our code deals the roles, keeps everyone's secrets and enforces the rules.
- **Roles stay hidden on death.** You find out who was who at the end, not when they die. This was the biggest balance lever (see below).
- **No kill on night 1.** The mafia start killing on night 2, so day 1 is all talk.
- **A day is a fixed number of turns,** not a timer: everyone speaks once (you can pass), a few accused or named players get to answer, then the vote opens. You can call the vote early.
- **Two optional roles,** Jester and Bodyguard, can replace villagers.

<a id="mafia-balance"></a>

### 1c. Balancing the agents

We ran batches of 20 to 40 AI-only games and changed one thing at a time, aiming for a village win rate of 45 to 55%, chats and personalities that read like people, and low API costs.

**Under the hood, start to finish:**

| Metric                                                           | First version  | Now        |
| ---------------------------------------------------------------- | -------------- | ---------- |
| Mafia voting for the same target                                 | 75%            | 29%        |
| Day 1 opens with "no one died" small talk                        | 18 of 20 games | 0 of 20    |
| Share of messages with stock phrases ("convenient", "staged"...) | 29%            | 16 to 18%  |
| Input served from cache                                          | 0%             | 67 to 73%  |
| Output tokens per vote / night call                              | ~165 / ~193    | ~70 / ~54  |
| Cost per game                                                    | $0.027         | **$0.016** |
| Moves still illegal after a retry                                | 0              | 0          |

The final reference run (40 games, 7 players each):

|                                    |                                             |
| ---------------------------------- | ------------------------------------------- |
| Village wins                       | **20 / 40 (50%)**                           |
| Game length                        | 2 days: 23, 3 days: 8, 4 days: 8, 5 days: 1 |
| Kills blocked by the doctor        | 31 / 67 (46%)                               |
| Slowest rounds (p95)               | votes and nights 3.96 s, first word 3.40 s  |

Hiding roles on death was the lever that mattered: with roles revealed, the village won 82% of a 40-game run; with them hidden, 55%. A revealed role exposes a mafia bluff as soon as the falsely accused player dies.

Along the way: 260+ automated tests, and a reference check that catches an agent quoting someone who never said it.

🧂 **Grain of salt:** 40 games is only good to about ±15 points, the village is AI (not a human), and over half the games end on day 2. We haven't tested whether that feels too short.

---

<a id="spy"></a>

## 🕵️ 2. Out of Place

Everyone knows where you are, except the spy. Ask the right questions, spot the one who's bluffing, or be the spy and work out the place before they catch you. You and 4 to 7 AI players.

<a id="spy-rules"></a>

### 2a. How a round goes

1. **Deal.** One player is the spy. Everyone else sees the same secret place, picked from 40 of our own in 10 clusters of look-alikes (for example hot spring, sauna, swimming pool, water park). With **place roles** on (the lobby's default), each civilian also gets a secret role there, like the lifeguard at the swimming pool. The spy sees nothing.
2. **Questions.** Each player still in asks one other player a question, and they answer. The spy can name the place at any point, even on someone else's turn.
3. **Vote.** After the last question, everyone votes for the spy. Then a new round starts with the players still in.

| What happens                              | Result                                                                                                    |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| The spy names the place, on anyone's turn | Right: spy wins. Wrong: civilians win                                                                     |
| The vote lands on the spy                 | The spy gets one last chance to name the place. Right: **draw**. Wrong: civilians win                     |
| The vote lands on a civilian              | They're out (everyone sees they were a civilian), and the spy has survived a vote                         |
| The vote ties                             | One revote among the tied players. Tie again: nobody is out, and the spy has survived a vote              |
| The spy survives **2 votes**              | Spy wins. The spy also wins as soon as only the spy and one civilian are left                             |

<a id="spy-differs"></a>

### 2b. How it differs from the original

Out of Place borrows one idea from Spyfall (see [credits](#credits)): a hidden location and one spy. The rest is our own.

|               | The original (roughly)     | Out of Place                                                                                           |
| ------------- | -------------------------- | ------------------------------------------------------------------------------------------------------ |
| Questions     | Free back-and-forth, timed | One question per player, in turns, in voting rounds                                                    |
| Location list | Everyone can see the list  | **The AIs get no list at all.** They guess in free text, and a rule-based matcher decides if it counts |
| Places        | The published locations    | Our own 40, grouped in look-alike clusters, with 400 roles we wrote                                    |
| Ending        | A guess or an accusation   | The spy must survive two votes; a last chance, a draw, and a tie revote                                |
| Human spy     | Sees the list              | Gets an optional list; the AI spy never does                                                           |

<a id="spy-balance"></a>

### 2c. Balancing the agents

The first version was broken in a very clear way: **the spy won all 60 games**. The civilians were giving the location away themselves, in their answers and even in their questions. So we fixed that with structure, not prompt wording:

| Step                     | What we changed                                              | Spy wins                                                                            |
| ------------------------ | ------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Baseline                 | 20 places, 2 questions each                                  | 100% (60/60)                                                                        |
| Open vote                | Anyone may call a vote early                                 | 93% (28/30), and nobody ever used it (0 of 265 chances)                             |
| Fewer questions          | One question each                                            | 97% (29/30)                                                                         |
| Look-alike places        | 40 places in 10 clusters of 4                                | 97% (29/30)                                                                         |
| **No location list**     | AIs guess in free text                                       | **83% (25/30)**, and the spy's chosen guesses dropped from 12 of 12 right to 6 of 9 |
| **Draw and revote**      | A right last-chance guess is a draw, tied votes get a revote | **67% wins, 75% spy score**                                                         |
| **Survive two votes**    | Voting rounds: the spy must survive 2 votes (the default now) | **62% spy score** over 60 games                                                     |

(Spy score = spy wins plus half of draws.)

**What we built to make the guessing fair:**

- A rule-based matcher: exact name, alias, extra descriptive words ("a big public swimming pool"), one-letter typos. "Airport" for "airport lounge" counts as wrong, and so does naming a different place.
- A judge model only for what's left over (17% of rulings), with every verdict saved so the same guess always gets the same answer.
- A hand audit of the rulings, an alias file reviewed line by line, and a rule that an empty reply never decides a game.

**Under the hood:** about $0.01 per game, per-call latency around 2 seconds at p95, and a clean prompt scan in every run: no AI prompt contains a place name except a civilian's own role card.

🧂 **Still open:** each run is 30 games (about ±15 points). With two votes, a round's vote lands on the spy about a third of the time (34 to 35%, against 15 to 18% by pure chance), and the spy still wins most games. Next experiment: everyone answers at once, so the spy can't echo what it just heard.

---

<a id="th"></a>

## 🐴 3. Trojan Horse (coming soon)

Not built yet, so no stats. It will be a hidden-role voting game for 5 to 10 seats on the same engine:

- **Teams.** A loyal majority against a small hidden team that knows each other, with a secret leader among them.
- **Each round.** The table elects a pair to pass the next policy. One of them draws from a hidden deck and passes cards to the other, so either of them can lie about what they saw.
- **Winning.** The loyal side wins by passing enough of its own policies or by unmasking the leader. The hidden team wins with enough of theirs, or by getting their leader elected once the game is far enough along.

The mechanics are adapted from Secret Hitler (credited below). The theme, names and every line of text will be our own.

---

<a id="ai"></a>

## 🤖 4. How the AIs work

Every agent, in every game, runs on the same engine, the same model, and the same API. The clever part is how each call is built.

<a id="ai-model"></a>

### 4a. The model and the API

|          |                                                                                                                                                                                    |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model    | **GPT-5.6 Luna**, OpenAI's fast and cheap tier: $0.20/1M input tokens, $1.20/1M output (Oct 2026)                                                                                  |
| Why Luna | Fast enough for live chat and cheap enough to run thousands of games, about $0.016 per Mafia game. Its bigger sibling, Terra, costs 10x more, which we tried but it wasn't needed! |
| API      | OpenAI's API with **structured outputs**: every call has a JSON schema, and replies stream in so a message types out as it's written, perfect for animation                        |
| Calls    | About 45 per Mafia game. Votes and night actions run in parallel, chat runs one speaker at a time                                                                                  |
| Memory   | None. The model remembers nothing between calls, so the server rebuilds what each agent knows on every call. Thankfully prompt-caching exists                                      |

<a id="ai-prompt"></a>

### 4b. Prompt layering

Every call is the same three layers, stacked in the same order:

| Layer                               | What's in it                                                                                               | Changes...    | Cached?            |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------- | ------------------ |
| **1. Shared rules** (~1,500 tokens) | The rules, every role guide, claim and accusation rules, voice guidance, the move formats                  | never         | yes                |
| **2. Persona**                      | Name, voice, three sample lines                                                                            | per character | yes, per character |
| **3. What each AI knows right now** | Their role card, the transcript so far, their private instruction for this turn, the task, any retry error | every call    | no                 |

We learnt that order matters, because OpenAI caches the _opening_ of a prompt automatically, and cached input costs about a tenth. So layer 1 has to be **identical** at the front of every call from every agent, and the details of the cache are where most of the engineering went:

- **One cache for the whole table.** Seven agents, one shared opening. Only the persona and the live view differ, so every agent's call hits the same cached block.
- **The role card moved out.** It used to sit inside the shared rules. Moving it to layer 3 keeps the front identical for every role.
- **The schema is part of the prompt.** The JSON schema is sent ahead of the messages, and ours used to change from agent to agent (the player lists dropped the speaker and the dead). Cache hit rate: 4%. Calls whose exact schema and persona had just been sent hit it 100%.
- **The fix.** One fixed schema per call type, with a constant list of all 8 cast names, and the legality checks moved into code.

The result:

|                                 | Before | After     |
| ------------------------------- | ------ | --------- |
| Input served from cache (Mafia) | 0%     | 67 to 73% |
| Cost per Mafia game             | $0.027 | $0.016    |

<a id="ai-moves"></a>

### 4c. Structured moves

| Call         | The model returns                                                                                                     | Output size |
| ------------ | --------------------------------------------------------------------------------------------------------------------- | ----------- |
| Discussion   | A message (25 words max, first so it can stream), a short private note, an optional role claim, and who it's accusing | ~225 tokens |
| Vote         | A vote target and nothing else                                                                                        | ~70 tokens  |
| Night action | An action and nothing else                                                                                            | ~55 tokens  |
| Out of Place | Ask (target + question), answer, a free-text place guess, or a vote                                                   | short       |

Names are a fixed list, but **legality is checked in code**: alive, not yourself, the doctor can't repeat a save, no kill on night 1. A bad move gets one retry with the reason, then a safe default move. Across every run, **0 moves were left illegal after a retry**.

<a id="ai-dice"></a>

### 4d. Archetypes: Code rolls the dice, the model writes the lines

Models are bad at "act 40% sneaky" and good at following one concrete instruction. So code rolls the dice and hands the model a private instruction for that turn:

- **Mafia:** each day, a seeded roll picks the team's plan: blend in, fake-claim detective, counterclaim, or split the votes.
- **Out of Place:** the spy either blends in or opens a guess window. Civilians either probe or stay vague.
- **The model never sees the dice.** It just writes the line.

It also makes games measurable: setups are replayable from a seed (roles, strategy rolls, turn order), although the AIs' wording isn't. Around that sit the guardrails:

- 🧾 **Claims are tracked.** The real detective can only claim real results, the mafia can fake them, and the game knows which is which.
- 🛡️ **Reference check.** An AI quoting someone who never said it gets sent back.
- 🔤 **Phrase budget.** Stock words like "convenient" are capped across the whole table.
- 🎯 **Guess matcher.** Free-text place guesses are ruled by exact names, aliases and typos first, with a judge model only for what's left, and every verdict is saved so the same guess always gets the same answer.

<a id="ai-settings"></a>

### 4e. Settings and logging

| Setting               | What it controls                                                                                                                                                                  |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model per call type   | Discussion, vote, night, ask, answer, guess and judge each map to a model in config. A role-based override exists (for example a bigger model for the mafia only), off by default |
| Max output tokens     | Tight caps on votes and nights, a larger one for free-text guesses                                                                                                                |
| Reasoning effort      | Kept low, since reasoning tokens bill as output and add delay                                                                                                                     |
| Deadlines and retries | Every call has a deadline, one retry, then a safe default move                                                                                                                    |
| Mode options          | The rules and strategy odds: fake-claim chance, counterclaim chance, split-vote chance, no night-1 kill, roles hidden on death, votes the spy must survive, tie revote            |

Every call logs its model, input, cached, output and reasoning tokens, cost, latency, and the role that made it, so any number in this README can be re-scored from the run files.

---

<a id="next"></a>

## 🗺️ 5. What's next

| Next                                                                    |            |
| ----------------------------------------------------------------------- | ---------- |
| Playable Out of Place in the browser                                    | done       |
| Lobby, AI cast, difficulty, How to Play pages, post-game review         | done       |
| A Mafia screen that paces itself, with Pause and a control center       | done       |
| Trojan Horse on the same engine                                         | next       |
| A link you can just play                                                | eventually |

<a id="credits"></a>

## 🙏 6. Credits and license

- **Mafia** was created by Dmitry Davidoff.
- **Out of Place** borrows the idea of a hidden location and one spy from **Spyfall**, designed by Alexandr Ushan and published by Hobby World.
- **Trojan Horse** will adapt mechanics from **Secret Hitler** by Mike Boxleiter, Tommy Maranges and Max Temkin, released under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

Kira's game names, places, roles, characters and text are our own; no text or art from those games is used.

Full plan and known issues: [docs/design.md](docs/design.md). How to run everything: [documentation.md](documentation.md).

License: [MIT](LICENSE).
