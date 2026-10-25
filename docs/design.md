# AI Social Games, Jackbox-Style: Design Doc

## Name: Kira

### Kira means to reckon, guess or estimate in Indonesian/Malay (the root of "berkira")

## Overview

This is a single-player, Jackbox-style game: you pick a game from a lobby, choose how many AI opponents to play against, and play a round of about ten minutes. The MVP ships three social-deduction games on one shared engine: Mafia, a fascist-themed hidden-role game with its own name and theme, and Impostor (Among Us style). Games built around CS 515 concepts follow after the MVP.

**Goals**

- A finished-product feel: lobby, game picker, an opponent-count slider (4 to 8 AI players), a recurring cast of named AI characters, and a results screen.
- One engine, many games: a new game is a config plus a resolver, not a rewrite.
- AI players that bluff, accuse and defend believably, without leaking secrets or breaking the rules.
- Fast: AI messages stream in like a live chat, with votes and night actions running in parallel.
- Cheap: measured at $0.016 per Mafia game with GPT-5.6 Luna on every call (see "Mafia reference" below).

**Non-goals (for now)**

- No multiplayer with other humans at launch; it is one player against AI.
- No voice, no 3D, no native mobile app; a responsive web page is enough.
- No fine-tuning or training of models; prompts and code only.
- No real-money features.

## Game modes

Every game is a config: roles, phases, who can talk to whom, what each player may see, how votes or bids resolve, and the win condition. The engine never changes between games. The first three games are the MVP; the rest follow in the order of the table.

| Game                              | Plays like                    | CS 515 concept                            | Build order |
| --------------------------------- | ----------------------------- | ----------------------------------------- | ----------- |
| Mafia                             | Mafia / Werewolf              | Plurality voting under hidden information | 1 (MVP)     |
| Fascist game (own name and theme) | Secret Hitler                 | Voting and strategic voting               | 2 (MVP)     |
| Impostor                          | Among Us                      | Hidden information and checkable alibis   | 3 (MVP)     |
| Rigged council                    | Avalon, The Resistance        | Voting rules, Gibbard-Satterthwaite       | 4           |
| Traitors                          | The Traitors (TV show)        | Voting plus a shared prize pot            | 5           |
| Haggle                            | Catan trading                 | Nash bargaining                           | 6           |
| Bluff                             | Coup, Liar's Dice, Poker      | Mixed Nash, minimax                       | 7           |
| Auction house                     | Monopoly auctions, Modern Art | VCG, second-price auctions                | 8           |
| Coalitions                        | Diplomacy, Survivor           | The core, Shapley value                   | 9           |
| Partners                          | Love Island recoupling        | Stable matching                           | 10          |
| Loot split                        | Snake draft                   | Fair allocation of indivisible goods      | 11          |

The three MVP games share one loop: hidden roles, discussion, votes. Impostor needs one extra system, a small simulated map with a movement log, so an alibi can be checked against what really happened; that makes it the most work of the three. Later games add mechanics such as offers, bids and rankings, each with its own resolver. Give the fascist game its own name, theme and text rather than copying the commercial game's.

**Licensing of borrowed mechanics.** Secret Hitler's rules are published under Creative Commons BY-NC-SA 4.0. If we reuse its mechanics, we must credit it (title, authors, license link), may not use them commercially, and must share adaptations under the same license. Every game name, role name, piece of flavor text and art in this repo must be our own before the repo goes public; the game picker currently shows "Secret Hitler" and "Spyfall" as placeholder titles and both must be renamed.

**A mode config contains**

- Roles and how many of each, by player count.
- Phases in order (for example night, day discussion, day vote), with a turn limit per phase.
- Visibility rules: public channel, private channels (for example, mafia only), and per-role secret knowledge.
- Actions allowed per phase, as structured choices the engine validates.
- A resolver function: how votes, bids or offers turn into outcomes.
- Win conditions, checked after every phase.

## Architecture

The game server is plain code and owns every fact: who has which role, who is alive, what was said and how people voted. LLMs are called only to produce one move for one player, from a view the server cuts for that player.

&#91;embedded content: architecture · client, game server, agent runner, OpenAI API\]

The highlighted box is the source of truth; the agent runner only ever receives a view of it and returns a move.

**Rules the code enforces**

- **Truth lives in code.** Roles, votes and night results sit in game state, never in a prompt history an LLM could misremember.
- **Per-player views.** The view builder sends the public transcript plus only what that player's role may know. A secret cannot leak because it was never sent.
- **Structured moves.** A discussion turn returns JSON with a public message, a public accusation, an optional role claim and private notes; a vote or night turn returns only an action. Code checks every field is legal, then resolves votes, bids or offers.
- **Modes are data.** The server reads a mode config and runs the same loop for every mode.
- **One logger.** Every model call records tokens, dollars and latency.

**Game loop**

1. The engine opens a phase (for example, day discussion).
2. For each player who acts: the view builder cuts a view, the agent runner builds the prompt and calls a model, and the referee validates the returned move.
3. When the phase ends, the referee resolves it (counts votes, applies the night kill), updates state, and checks win conditions.
4. The loop repeats until a win condition fires.

**Phases, timeouts and retries**

- **Three phase types.** Sequential (one actor at a time, like discussion), simultaneous (every actor submits, then the resolver runs, like votes and night actions), and automatic (code only, like the morning announcement).
- **Transitions are config.** Each game defines a small state machine: phase, then next phase, chosen by the resolver's result (for example, after the vote go to night unless a win condition fires).
- **Timeouts.** Every model call has a 10-second deadline. On a timeout, invalid JSON or an illegal choice, retry once with the reason, then apply the game's default move (abstain, skip, or a random legal action). A dropped connection is waited out with backoff, and the game stops rather than playing on with defaults if the API stays unreachable.
- **Pure resolvers.** A resolver is a function of state and submitted actions, so the same inputs always give the same outcome.
- **Replayable games.** Use a seeded random generator and log every model input and output, so any game can be replayed to debug it.

**Stack:** Python 3.14 (managed with uv) with FastAPI on the server, and React 18 with TypeScript, Vite and CSS modules on the client (no UI framework). The engine is a pure Python package with no network access, and Pydantic defines every game config, move and model-output schema. Model calls use OpenAI chat completions with strict JSON-schema structured output and streaming. Live chat uses Server-Sent Events, parallel model calls use asyncio, and the cost log goes to SQLite. The OpenAI key stays on the server only, and no agent framework is used: a small wrapper makes each model call. Lint and format: ruff (line length 120).

**Repo layout**

```
backend/src/engine/   pure Python, no network: state, referee, view builder, game configs, Mafia mode
backend/src/agents/   personas, prompt builder, output schemas, checks, agent runner, OpenAI client, cost log
backend/src/server/   FastAPI app and SSE routes, per-game orchestrator, self-play, run summaries and metrics
backend/scripts/      report.py: gate and balance metrics from the cost log or a self-play run
backend/tests/        pytest: leak test, random-bot games, golden games (tests/golden/), checks, API
web/                  React app: game select, lobby, characters, game screen, results and review
```

The engine package never imports the network or the OpenAI SDK, so it can be tested with random bots before any model is involved.

## Agent design

Each LLM player is a stateless function that code calls with a filtered view of the game and that returns one structured move. The agent holds no truth; the engine does. This is what keeps the game fair and the cost low.

**What one agent is made of**

- **Persona (static):** name, voice (for example "The Analyst"), speaking style, a voice card of three sample lines, and three knobs (talkative, suspicious, good liar) that difficulty shifts. Identical for that character all game, so it caches.
- **Role card (private):** the agent's role, its win condition, and any secret it legitimately knows (for example, who its fellow impostors are).
- **Observation (built by code each turn):** the public transcript since its last turn, its own private events (such as a detective result), the current phase, and the list of legal actions. Nothing else.
- **Belief notes (private, carried between turns):** a short structured record the agent writes itself: a suspicion score per player, claims it has heard, and its current plan. Code stores it and feeds it back next turn; no other agent ever sees it.

**One turn**

1. The engine picks whose turn it is and builds that agent's observation.
2. A discussion turn returns JSON with `say` first (so it streams), then `accuses` (one player or null, shown publicly as "Bram → Kit"), `claim` (null or a role claim such as detective with a target and result) and `state` (private notes: suspicion per player, claims heard, own claims, plan). A vote or night turn returns only `{"action": ...}`. No free-form reasoning is returned.
3. Code validates every field: the action is legal, the accused is alive and not the speaker, a real detective can only claim results it actually got. The message is also checked (texting style, a 25-word cap, breaking character, statements attributed to players who never made them, used-up stock phrases). A failure gets one retry with the reason, then a safe default.
4. The engine appends `say`, records the claim and accusation, applies the action, and stores `state` as the agent's notes for its next turn. Vote and night turns leave the notes unchanged.

**Why secret-holders need extra care**

Untouched LLMs are bad at this game: they are too honest, too agreeable, and they pile onto the same suspect. The fixes are built into the design, not hoped for.

| Failure                                                            | Fix                                                                                                                                    |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| A bad-guy role (mafia or impostor) confesses or contradicts itself | Private notes include an explicit deception plan and a list of what it has already claimed; the observation reminds it of those claims |
| Everyone votes for the loudest player                              | Persona seeds different suspicion biases; the engine shows each agent only its own prior votes, not a consensus                        |
| Invented evidence ("I saw X at night")                             | A reference check compares every message with the whole game and the claims log, and retries one that quotes a player who never spoke or names a role claim nobody made |
| Agents agree on everything                                         | Persona includes a stubbornness trait and a rule to challenge at least one claim per day                                               |
| Rambling or repeating                                              | 25-word cap, a no-repeat instruction with the agent's last message, and a table-wide cap of 2 uses per game for each stock phrase |
| Breaking character as an AI                                        | Persona rule plus a cheap output check before the message is posted                                                                    |
| Leaking information it should not have                             | Agents only ever receive what their role permits, so there is nothing extra to leak                                                    |

**Memory across days**

The transcript grows every round. Daily summaries are **not built yet**: the prompt carries the last 120 lines of the record, which is enough for Mafia games of 2 to 5 days. If a later game runs longer, a cheap model can compress each day into a few lines per agent.

**Model tiers**

GPT-5.6 Luna runs every call type, with reasoning effort low. The model is one config value per call type (discussion, vote, night), plus optional per-role overrides (`MODEL_MAFIA_DISCUSSION`, `MODEL_MAFIA_NIGHT`) that are off by default. Terra was not adopted: a diagnosis of 57 failed mafia bluffs found 53 were structural (exposed by role flips or the real detective) and only 1 was wording, so a better writer would not have fixed them.

**How calls are scheduled**

Each AI player makes its own call, but only when it has something to do.

1. **Night, in parallel.** Only role holders get a call (for example, the mafia pick a target and the doctor picks a save). They fire at once, so the wait is one call, and a night animation hides it.
2. **Morning, no model call.** Code resolves the night and announces the result.
3. **Discussion, one speaker at a time.** Round 1: every living player speaks once, in a seeded random order (you can pass). Round 2: up to 3 extra AI speakers, accused or addressed players first. Each gets one call, and the message streams into the chat as it is written. If you speak mid-round, code re-picks who responds. Anyone alive can call the vote early.
4. **Vote, in parallel.** Every living AI votes at once. The screen reveals votes one by one while slower calls finish.
A measured 7-player game is about 45 calls (about 23 discussion, 15 vote, 7 night); only the discussion calls depend on each other.

**Speed levers**

- Cap messages at 25 words, keep private notes short, and give vote and night calls an action-only schema (about 65 and 45 output tokens).
- Caching: see "Prompt layout and caching" below.
- Cap speakers per round at 3 or 4, so latency does not grow with the number of opponents.
- After the MVP: villagers share no secrets, so one call can write several villagers' lines for a round while secret-holders keep their own calls. This is the biggest speed and cost win, but villagers may sound more alike.

## Cost model

**Measured:** $0.016 per 7-player game on all-Luna with caching (40-game reference, below). The estimates that follow were written before the build and are kept for the Terra comparison.

**Assumptions (pre-build estimates)**

- 7 players: you plus 6 LLMs, about 3 game days, about 54 LLM calls per game.
- About 130,000 input tokens and 10,000 output tokens per game in total.
- Discussion call: about 2,500 tokens in (1,200 of them a fixed persona and rules prefix) and 250 out. Vote call: about 2,800 in, 100 out. Night action: about 1,800 in, 80 out. Daily summary: about 1,500 in, 200 out.

**API prices used** (per million tokens, input / output)

| Model         | Input | Output | Cached input |
| ------------- | ----- | ------ | ------------ |
| GPT-5.6 Luna  | $0.20 | $1.20  | $0.02        |
| GPT-5.6 Terra | $2.00 | $12.00 | $0.20        |

These are the rates OpenAI set on July 30, 2026 ([OpenAI announcement](https://openai.com/blog/advancing-the-price-performance-frontier-with-gpt-5-6), [price-cut coverage](https://letsdatascience.com/news/openai-cuts-gpt-56-terra-and-luna-prices-ec2badb6)). OpenAI calls Luna its fastest and most affordable model and Terra its balanced one. Cached-input prices come from a reseller's [price-update note](https://docs.apiyi.com/en/live/2026-07/gpt-5-6-terra-luna-price-cut), so verify them on OpenAI's pricing page before relying on them.

**Cost per game, no caching**

| Setup                          | Who runs what                                                      | Cost per game |
| ------------------------------ | ------------------------------------------------------------------ | ------------- |
| **All Luna (default)**         | Every call                                                         | about $0.04   |
| Luna plus Terra for mafia      | Terra only when a mafia player speaks                              | about $0.11   |
| Luna plus Terra for discussion | Terra for all discussion; Luna for votes, night actions, summaries | about $0.25   |
| All Terra                      | Every call                                                         | about $0.39   |

Caching the fixed persona and rules prefix lowers input cost further, since cached input is billed at about a tenth of normal input on both models. Treat the figures above as upper bounds with no caching, and capping speakers at 3 or 4 per round cuts them again.

**What that means for a budget**

- 200 playtest games on all-Luna: about $8.
- 100 games a month on all-Luna: about $4; with Terra for mafia: about $11; with Terra for all discussion: about $25.
- Building the game with a coding assistant is a separate cost from running it.

**Cost levers, biggest first**

1. **Model per call type.** Luna for votes, night actions and summaries; upgrade only the call types that read badly.
2. **Cap output.** 60-word messages and short structured state updates. Keep reasoning effort low, since reasoning adds both delay and cost.
3. **Cache the fixed prefix.** Persona, rules and game config repeat on every call of a game.
4. **Compress history daily.** Otherwise input grows with every round.
5. **Skip calls the code can answer.** If a player is dead, silent by rule, or has one legal action, no call is made.
6. **Fewer speakers per round.** Only 3 or 4 AI players speak each round, chosen by who was accused or asked a question.
7. **Batch villager chatter (after the MVP).** One call writes several villagers' lines, since they share no secrets.

**Guardrails**

- A hard token budget per game; when hit, remaining votes use a cheap default and the game finishes.
- A daily spending cap on the API key, and a per-room limit on games started.
- Log tokens and dollars per call from day one, so the estimates above get replaced by real numbers.

## Prompt layout and caching

OpenAI caches a prompt prefix of 1,024 tokens or more, and the response schema sits in front of the messages, so both must be byte-identical for caching to apply.

1. **Shared block** (about 1,500 tokens): game rules, every role guide, how to play, voice guidance and the answer formats. Identical for every agent, role and game of a setting.
2. **Persona block:** the character and voice card, identical for that character all game.
3. **Dynamic part:** the table, your secret role, the record, claims, accusations, your notes and the task.

The JSON schema is **one fixed schema per call type**, listing every cast name (plus a human player's name), never the per-call legal subset. Who may actually be picked (alive, not yourself, no teammate kill, no repeat doctor save) is checked in code, with one retry, then a default. This raised the cached share of input from 28% / 10% / 5% (discussion / vote / night) to 73% / 67% / 73% and cut cost per game from $0.027 to $0.016.

## Milestones

The build runs in five milestones. Each ends at a gate that must pass before the next one starts, and each stands alone if you need to pause for exams.

&#91;embedded content: roadmap · 5 milestones, 5 gates\]

The first two gates matter most: together they test whether cheap LLM players are fun before any new mode is built.

**Status (October 2026):** milestone 1 is done and Mafia is frozen at tag `v0.1-mafia`; most of milestone 2's product shell is built (lobby, game picker, cast, results, review) but not deployed or playtested by people. Next: a second game.

1. **Mafia against AI players.** *(Done.)* Build the engine (state, phases, referee, game config loader), the view builder with a test proving no AI player's view contains another player's secret, AI players on GPT-5.6 Luna with personas and structured belief state, parallel votes and night actions, streamed discussion, and per-call token, dollar and latency logging. Gate: 20 full games finish, and cost, p95 latency, invalid-action rate and round length are measured against the targets below.
2. **Product shell and quality pass.** *(Built except deploy, daily summaries and the human rubric.)* Build the lobby, game picker, opponent-count slider (4 to 8), a recurring cast of named AI characters and a results screen, then deploy it. Fix what the 20 games showed: mafia deception plans, GPT-5.6 Terra for any call type that reads badly, daily summaries, prefix caching. Gate: at least five people score the rubric below, the model per call type is decided from measured numbers, and a friend can play a round from a link.
3. **Fascist game.** Add the election and policy-deck resolvers, with your own name and theme. Gate: it plays through on the same engine with only a new config and resolver.
4. **Impostor.** Add a small simulated map, a movement log and a meeting phase, so an alibi can be checked against the truth. Gate: an AI can lie about where it was and get caught by the log.
5. **CS 515 games, one at a time.** Rigged council first (plurality, ranked choice, Borda), then Traitors, Haggle, Bluff, Auction house and the rest, in the order of the games table. Multiplayer with other humans can come after. Gate for each: the game's concept visibly shows up in play.

## Targets and playtest rubric

These turn "fast, cheap and fun" into numbers. They are proposals to adjust once milestone 1 gives real measurements.

| Metric                                          | Target                | Mafia reference (40 games)            |
| ----------------------------------------------- | --------------------- | ------------------------------------- |
| Time until an AI message starts streaming (p95) | under 2 seconds       | 3.40 s (miss)                         |
| A vote or night round, all AI answers in (p95)  | under 4 seconds       | 3.96 s (pass)                         |
| Moves still invalid after one retry             | under 1%              | 0 of 1,788 turns (pass)               |
| Length of one round                             | 8 to 12 minutes       | not measured: self-play has no pauses |
| Cost per completed game                         | at most $0.15         | $0.016 avg, $0.039 max (pass)         |
| Average human rubric score, every row below     | at least 3.5 out of 5 | not run yet                           |

**Human playtest rubric.** At least five people each play three games, then rate each statement from 1 (disagree) to 5 (agree).

| Statement                                              | What it checks         |
| ------------------------------------------------------ | ---------------------- |
| The AI players' bluffs were believable.                | Believable deception   |
| I could tell the AI players apart without their names. | Distinct personalities |
| The AI players' votes made sense given the discussion. | Strategic voting       |
| The AI players did not repeat themselves.              | Repetition             |
| I would play another round.                            | Fun                    |

## Risks and open questions

The biggest risk is that cheap models make boring or unconvincing players, which is why the first two milestones end with a quality check before any new mode is built.

| Risk                                   | Why it matters                                                                   | Mitigation                                                                                                                     |
| -------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Luna players feel flat or robotic      | The game is only fun if players read as people                                   | Run the human rubric; upgrade weak call types to GPT-5.6 Terra (about $0.11 per game for mafia only, $0.25 for all discussion) |
| AI players all sound alike             | Kills the guessing game                                                          | Distinct personas with sample lines, varied suspicion biases, different speaking lengths                                       |
| Latency                                | Discussion calls depend on earlier messages, so they run one after another       | Parallel votes and night actions, streamed messages, 3 or 4 speakers per round; hold to the p95 targets                        |
| Costs run higher than estimated        | The estimates are untested                                                       | Log tokens per call from day one; hard per-game budget and daily key cap                                                       |
| Scope creep across games               | Each new game needs its own resolver, and Impostor needs a simulated map         | No second game until Mafia passes its gates; Impostor third                                                                    |
| Fascist game too close to the original | Reusing its name, art or text could cause problems                               | Own name, theme and text; keep only the hidden-role mechanics                                                                  |
| Model names and prices shift quickly   | This doc's first draft named a model generation that had already been superseded | Keep model names in config, and recheck OpenAI's pricing page before each build                                                |
| API key exposed or abused              | A public link can drain credits                                                  | Keep the key on the server only; rate-limit rounds; set a spending cap                                                         |
| Midterm season takes the hours         | Only so many weekend hours                                                       | Plan on a few weekends for milestone 1; pause freely, since each milestone stands alone                                        |

**Open questions**

- Impostor: a text-only map, or a simple visual one?
- After human playtesting, does any call type need Terra?
- Balance against human players (all measurements so far are AI against AI).
- Answered: Mafia ships with villagers, mafia, detective and doctor, plus optional jester and bodyguard; the cast is 8 named characters in the "Lantern Hour" style (design/UI_SPEC.md); the frontend is React with Vite.

## Mafia reference (frozen at v0.1-mafia)

Mafia's engine, prompts, schemas and options are frozen. `backend/tests/test_golden.py` replays three seeded games with the fake model and fails if any event changes; work on the next game must keep it passing.

**Settings**

| Setting | Value | Where |
| --- | --- | --- |
| Players | 5 to 9 (you plus 4 to 8 AI); 1 mafia at 5 to 6 players, 2 at 7 to 9; 1 detective, 1 doctor, the rest villagers | `modes/mafia.py` |
| Optional roles | jester, bodyguard (each replaces a villager), off by default | lobby |
| Roles on death | hidden; shown only at game end (results and review) | `REVEAL_ROLE_ON_DEATH=false` |
| Night 1 | no kill; detective and doctor still act | `skip_first_night_kill` |
| Doctor | may not protect the same player two nights running (the night-1 save doesn't count) | `doctor_no_repeat` |
| Discussion | round 1: everyone once; round 2: up to 3 extra AI speakers; vote can be called early | phase config |
| Mafia daily plan (seeded) | fake-claim detective day 1: 0.5, later days 0.15; clear a partner instead: 0.25; counterclaim a claim naming the team: 0.25; split the vote: 0.6; night kill prefers a claimed detective, then a cleared player, then the most trusted | mode options |
| Real detective with a mafia result | reveals on day 1 with probability 0.5, otherwise day 2 or when named | `detective_day1_claim_p` |
| Model | gpt-5.6-luna for every call type, reasoning effort low; per-role overrides off | `settings.py` |
| Output caps | discussion 1,500 tokens (25-word message), vote and night 400 | `settings.py` |
| Stock-phrase cap | 2 uses per game across the table: convenient, staged, pile-on/dogpile, leap, proves nothing, lazy, reeks, too neat, tidy | `PHRASE_CAP` |
| Call deadline | 10 s, one retry, then a default move | `settings.py` |

**40-game reference** (self-play, 7 players, all AI, `backend/runs/merged/20261022-hidden-ref-40.jsonl`, not committed)

| Metric | Value |
| --- | --- |
| Win rate | village 20 of 40 (50%), mafia 20 of 40 |
| Game length | 2 days ×23, 3 days ×8, 4 days ×8, 5 days ×1 |
| Cost | $0.016 per game on average, $0.039 max, $0.64 for the run |
| Calls per game | 44.8 (discussion 22.6, vote 15.1, night 7.1) |
| Cached share of input | discussion 73%, vote 67%, night 73% |
| Latency, discussion call | p50 3.10 s, p95 4.48 s |
| Latency, vote call | p50 1.64 s, p95 3.25 s |
| Latency, night call | p50 1.41 s, p95 3.26 s |
| First streamed token | p50 2.01 s, p95 3.40 s |
| Vote or night round, all AI in | p50 2.36 s, p95 3.96 s |
| Output tokens per call | discussion 226, vote 70, night 54 |
| Retries | 5 (discussion 1, vote 4, night 0); 0 timeouts |
| First-try rejections vs invalid after retry | 5 vs 0 (of 1,788 turns) |
| Reference-check flags | 0 |
| Kills blocked by the doctor | 31 of 67 (46%) |
| Mafia voting the same target | 21 of 72 vote rounds (29%) |

**What moved the balance.** With roles revealed on death, the village won 70 to 90% of games across four tuning levers (counterclaim rules, detective timing, more fake claims, smarter night kills); none of them brought it into range. Hiding roles on death was the lever that mattered: village 82% with roles revealed against 55% hidden, in two 40-game runs with nothing else changed. A revealed role exposes a mafia bluff as soon as the falsely accused player flips; without it, 9 of 22 first fake claims survived the whole game against 0 of 11.

**Known issues**

- **Short games:** 23 of 40 games end on day 2, the earliest possible end at 7 players.
- **Slow first word:** first-token p95 is 3.40 s against a 2 s target, and rose from 2.89 s when the fixed schemas (which list the whole cast) arrived. Idea: prefetch the next speaker's message while the current one is shown.
- **Doctor blocks a lot:** 46% of night kills are blocked.
- **Balance is AI against AI:** every number above is from self-play; nothing has been measured against human players yet.
- **Round length is not measured:** self-play has no reading pauses, so the 8 to 12 minute target is untested.

**Before any deploy** (not fixed: Mafia is frozen, and these are deploy work)

- **No production run command.** The documented command uses `--reload`, which is for development only; a production command without it is needed.
- **The rate limit counts by IP.** Behind a proxy every player would share one IP, so the limit should read the forwarded client address.
- **Finished games are never removed from memory.** The server keeps every game until it restarts.
- **Anyone with a game ID can watch or drive that game.** IDs are random (40 bits) and there is no per-player token.
- **Your status messages include your own secret plan** when you are mafia or the detective. It is your own information and the UI doesn't show it, but it reaches the browser.
- **Player text goes into AI prompts word for word**, so prompt injection is possible. Answers are checked against fixed schemas, so the worst case is odd AI chat, not a broken game.
- **The input-validation step for player text is not built yet.** Only a 400-character cap applies; there is no check of what the human types before it reaches other players' prompts.

## Change log

- **v0.1-mafia** (October 2026): Mafia frozen. Engine with per-player views and a leak test; Lantern Hour web UI (game select, lobby with house rules and advanced cast settings, characters, game screen with a running chat and always-open notes, results and review); 8 named characters with voices and voice cards; role claims with a claims log and judged detective claims; seeded mafia team plans; public accusations; reference check against the whole game; stock-phrase cap; doctor no-repeat; no night-1 kill; roles hidden on death by default; three-part prompt with fixed schemas for caching; cost, latency and balance metrics per run; golden games.
- Earlier the project was called Berkira; renamed to Kira.
