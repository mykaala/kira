<p align="center">
  <img src="design/kira_banner.png" alt="Kira — Three games of trust and betrayal" width="100%">
</p>

**Pick from Mafia, Secret Hitler, and Spyfall. But every other seat on the table is an agent with an archetype, a memory, and something to hide.**

> 🚧 **Status:** Mafia and Spyfall now work and were balanced in self-play (stats below). A Secret Hitler-style game is next. Not deployed yet.

## 📚 Table of contents

1. [Mafia](#mafia)
   - 1a. [How a round goes](#mafia-rules)
   - 1b. [How it differs from the real game](#mafia-differs)
   - 1c. [Balancing the agents](#mafia-balance)
2. [Spyfall](#spy)
   - 2a. [How a round goes](#spy-rules)
   - 2b. [How it differs from Spyfall](#spy-differs)
   - 2c. [Balancing the agents](#spy-balance)
3. [Secret Hitler-style (planned)](#sh)
4. [How the AIs work](#ai)
   - 4a. [The model and the API](#ai-model)
   - 4b. [Prompt layering](#ai-prompt)
   - 4c. [Structured moves](#ai-moves)
   - 4d. [Code rolls the dice](#ai-dice)
   - 4e. [Settings and logging](#ai-settings)
5. [What's next](#next)
6. [Credits and license](#credits)

---

<a id="mafia"></a>

## 🎲 1. Mafia

You and 6-8 agents. Two of you are mafia and lying to the villagers. Figure out who before the village runs out of people.

<a id="mafia-rules"></a>

### 1a. How a round goes

**Night** (kill, save, check) → **Morning** (who died?) → **Chat** (accuse, defend, claim a role) → **Vote** someone out → repeat.

The village wins when the mafia are gone. The mafia win when they catch up to the town.

| Role                 | How many | What they do                             |
| -------------------- | -------- | ---------------------------------------- |
| 🦹‍♂️ Mafia             | 1-2      | Know each other. Kill one player a night |
| 🕵️‍♂️ Detective         | 1        | Checks one player a night: mafia or not  |
| 👩‍⚕️ Doctor            | 1        | Protects one player a night              |
| 🕵️ Villager          | 3-4      | Talk, think, vote                        |
| 🃏 Jester (optional) | 1        | Tries to get themselves voted out        |

<a id="mafia-differs"></a>

### 1b. How it differs from the real game

No need for a host or moderator, our code deals roles, keeps everyone's secrets, and enforce the rules. Jester

<a id="mafia-balance"></a>

### 1c. Balancing the agents

We ran thousands of AI-only games and changed one thing at a time to get a village win rate of 45%-55%, as well as made the chats and personalities as human-like as possible while keeping API costs low.

**Under the hood, start to finish:**

| Metric                                                           | First version  | Now        |
| ---------------------------------------------------------------- | -------------- | ---------- |
| Mafia voting for the same target                                 | 75%            | 29%        |
| Day 1 opens with "no one died" small talk                        | 18 of 20 games | 0 of 20    |
| Share of messages with stock phrases ("convenient", "staged"...) | 29%            | 16 to 18%  |
| Input served from cache                                          | 0%             | 67 to 73%  |
| Output tokens per vote / night call                              | ~165 / ~193    | ~65 / ~55  |
| Cost per game                                                    | $0.027         | **$0.016** |
| Moves still illegal after a retry                                | 0              | 0          |

The final reference run (40 games, 7 players each):

|                                    |                                             |
| ---------------------------------- | ------------------------------------------- |
| Village wins                       | **20 / 40 (50%)**                           |
| Game length                        | 2 days: 23, 3 days: 8, 4 days: 8, 5 days: 1 |
| Mafia fake-claimed detective first | 12 games, 5 never got voted out             |
| Doctor blocked a kill              | 31 / 67 (46%)                               |
| Slowest rounds (p95)               | votes and nights 3.96 s, first word 3.40 s  |

Along the way: more than 10,000 model calls, 200+ automated tests, and a reference-check that catches an agent quoting someone who never said it.

🧂 **Grain of salt:** 40 games is only good to about ±15 points, the village is AI (not a human), and over half the games end on day 2. We haven't tested if that feels too short.

---

<a id="spy"></a>

## 🕵️ 2. Spyfall

Everyone knows where you are except the spy. Ask the right questions, spot the one who's bluffing, or be the spy and work out the place before they catch you.

<a id="spy-rules"></a>

### 2a. How a round goes

1. **Deal.** One player is the spy. Everyone else sees the same secret place, picked from 40 of our own in 10 clusters of look-alikes (for example hot spring, sauna, swimming pool, water park). The spy sees nothing.
2. **Questions.** Each player asks one other player a question, and they answer. The spy can name the place at any point, even on someone else's turn.
3. **Vote.** After the last question, everyone votes for the spy.

| What happens                              | Result                                                                                |
| ----------------------------------------- | ------------------------------------------------------------------------------------- |
| The spy names the place, on anyone's turn | Right: spy wins. Wrong: civilians win                                                 |
| The vote lands on the spy                 | The spy gets one last chance to name the place. Right: **draw**. Wrong: civilians win |
| The vote lands on a civilian              | Spy wins                                                                              |
| The vote ties                             | One revote among the tied players. Tie again: spy wins                                |

<a id="spy-differs"></a>

### 2b. How it differs from Spyfall

|               | Spyfall (roughly)          | Kira                                                                                                   |
| ------------- | -------------------------- | ------------------------------------------------------------------------------------------------------ |
| Questions     | Free back-and-forth, timed | One question per player, in turns                                                                      |
| Location list | Everyone can see the list  | **The AIs get no list at all.** They guess in free text, and a rule-based matcher decides if it counts |
| Places        | The published locations    | Our own 40, grouped in look-alike clusters                                                             |
| Ending        | A guess or an accusation   | A last chance, a draw, and a tie revote                                                                |
| Human spy     | Sees the list              | Gets an optional list; the AI spy never does                                                           |

<a id="spy-balance"></a>

### 2c. Balancing the agents

The first version was broken in a very clear way: **the spy won all 60 games**. The civilians were giving the location away themselves, in their answers and even in their questions. So we fixed that with structure, not prompt wording:

| Step                 | What we changed                                              | Spy wins                                                                            |
| -------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Baseline             | 20 places, 2 questions each                                  | 100% (60/60)                                                                        |
| Open vote            | Anyone may call a vote early                                 | 93% (28/30), and nobody ever used it (0 of 265 chances)                             |
| Fewer questions      | One question each                                            | 97% (29/30)                                                                         |
| Look-alike places    | 40 places in 10 clusters of 4                                | 97% (29/30)                                                                         |
| **No location list** | AIs guess in free text                                       | **83% (25/30)**, and the spy's chosen guesses dropped from 12 of 12 right to 6 of 9 |
| **Draw and revote**  | A right last-chance guess is a draw, tied votes get a revote | **67% wins, 75% spy score**                                                         |

**What we built to make the guessing fair:**

- A rule-based matcher: exact name, alias, extra descriptive words ("a big public swimming pool"), one-letter typos. "Airport" for "airport lounge" counts as wrong, and so does naming a different place.
- A judge model only for what's left over (17% of rulings), with every verdict saved so the same guess always gets the same answer.
- A hand audit of the rulings, an alias file reviewed line by line, and a rule that an empty reply never decides a game.

**Under the hood:** about $0.004 per game in-game, cached input at 76 to 86%, per-call latency around 2 seconds at p95, and a clean prompt scan in every run.

🧂 **Still open:** each run is 30 games (about ±15 points), and the table's vote only finds the spy 14 to 22% of the time against about 10% by pure chance. Next experiment: everyone answers at once, so the spy can't echo what it just heard.

---

<a id="sh"></a>

## 🏛️ 3. Secret Hitler-style (planned)

Not built yet, so no stats. Here are the rules we're adapting:

- **Teams.** Liberals (the majority) against Fascists (a small team that knows each other), plus a secret leader on the Fascist side. In small games the leader knows the Fascists. In bigger ones, they don't.
- **Each round.** The President picks a Chancellor, and everyone votes yes or no on the pair. If it fails three times in a row, the top policy card is enacted at random.
- **Policies.** The President secretly draws 3 cards and discards 1. The Chancellor gets the other 2, discards 1, and enacts the last. The deck has 6 Liberal and 11 Fascist cards, so lying about what you drew is the whole game.
- **Powers.** Every Fascist card enacted unlocks stronger powers: investigate a loyalty, call a special election, peek at the deck, execute a player.
- **Winning.** Liberals win with 5 Liberal policies or by killing the leader. Fascists win with 6 Fascist policies, or by getting the leader elected Chancellor after 3 Fascist policies.

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
| Cached input (Spyfall)          | n/a    | 76 to 86% |

<a id="ai-moves"></a>

### 4c. Structured moves

| Call         | The model returns                                                                                                     | Output size |
| ------------ | --------------------------------------------------------------------------------------------------------------------- | ----------- |
| Discussion   | A message (25 words max, first so it can stream), a short private note, an optional role claim, and who it's accusing | ~200 tokens |
| Vote         | A vote target and nothing else                                                                                        | ~65 tokens  |
| Night action | An action and nothing else                                                                                            | ~55 tokens  |
| Spyfall      | Ask (target + question), answer, a free-text place guess, or a vote                                                   | short       |

Names are a fixed list, but **legality is checked in code**: alive, not yourself, the doctor can't repeat a save, no kill on night 1. A bad move gets one retry with the reason, then a safe default move. Across every run, **0 moves were left illegal after a retry**.

<a id="ai-dice"></a>

### 4d. Archetypes: Code rolls the dice, the model writes the lines

Models are bad at "act 40% sneaky" and good at following one concrete instruction. So code rolls the dice and hands the model a private instruction for that turn:

- **Mafia:** each day, a seeded roll picks the team's plan: blend in, fake-claim detective, counterclaim, or split the votes.
- **Spyfall:** the spy either blends in or opens a guess window. Civilians either probe or stay vague.
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
| Mode options          | The rules and strategy odds: fake-claim chance, counterclaim chance, split-vote chance, no night-1 kill, roles hidden on death, tie revote                                        |

Every call logs its model, input, cached, output and reasoning tokens, cost, latency, and the role that made it, so any number in this README can be re-scored from the run files.

---

<a id="next"></a>

## 🗺️ 5. What's next

| Next                                                                    |            |
| ----------------------------------------------------------------------- | ---------- |
| Playable Spyfall in the browser                                         | done       |
| Lobby, AI cast, difficulty, How to Play pages, post-game review         | done       |
| Secret Hitler-style game on the same engine                             | next       |
| A link you can just play                                                | eventually |

<a id="credits"></a>

## 🙏 6. Credits and license

Mafia was created by Dmitry Davidoff. Spyfall was designed by Alexandr Ushan and published by Hobby World. Secret Hitler is released under CC BY-NC-SA 4.0 by its creators. Game names, text, and locations in Kira are placeholders and will be replaced with our own.

Full plan and known issues: [docs/design.md](docs/design.md). License: MIT.
