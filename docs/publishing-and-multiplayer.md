# Publishing and multiplayer plan

*Written Oct 27, 2026. Prices and platform limits change often, so re-check each vendor's page before committing money.*

## 1. Three layers of publishing

| Layer | What it means | Status |
| --- | --- | --- |
| **1. The code** | Public GitHub repo, clean README, a write-up | Next, via the pre-public checklist |
| **2. A playable link** | A hosted app strangers can open | Needs the hosting, cost and safety work in sections 2 and 3 |
| **3. The story** | Demo video, a post on the balancing method, portfolio entry | Easy once layer 2 exists |

Do them in order. The repo doesn't need a live link, and the link doesn't need a launch campaign.

## 2. Layer 2: the playable link

### 2.1 What the server needs

- An **always-on container with one worker.** Each game (and later each room) lives in memory, and updates stream over SSE.
- **HTTPS and a domain.**
- Not a serverless function. Vercel now offers native WebSockets in public beta, but [connections are pinned to one function for its maximum duration, later connections may land on a different function, and Vercel recommends Redis for durable state](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections). See also [this write-up](https://ably.com/vercel/websockets-on-vercel). Rooms are all state, so we'd have to move every game out of memory and handle forced reconnects. A long-lived container is simpler.
- Vercel is still fine for hosting the static frontend, if we ever want that split.

### 2.2 Hosting options (mid-2026 third-party comparisons; verify)

| Option | Reported cost | Catch |
| --- | --- | --- |
| Render free tier | $0 | [Sleeps after 15 minutes idle, 30 to 50 second wake-up](https://www.kunalganglani.com/blog/render-vs-railway-2026) |
| Render Starter | $7/month | Fixed price, no cold starts |
| Railway Hobby | $5/month, includes $5 of usage | [Credit card required since March 2026](https://sota.io/blog/railway-vs-render-vs-fly-pricing-2026) |
| Fly.io | From about $1.94/month for the smallest VM, about $7/month for a common tier ([source](https://tech-insider.org/render-vs-railway-vs-fly-io-2026/)) | [No free tier for new accounts](https://agentdeals.dev/railway-vs-render) |

Expect **$5 to $7 a month** for hosting. Open item: check whether the GitHub Student Developer Pack still includes hosting credits or a free domain (not verified).

### 2.3 API cost

Per-game cost with GPT-5.6 Luna, from our own runs:

| Game | In-game cost per game |
| --- | --- |
| Mafia | about $0.016 |
| Out of Place | about $0.007 (K=2 pooled run: $0.0097 including offline judges, which won't run in production) |

| Games per month | Mafia | Out of Place |
| --- | --- | --- |
| 100 | $1.60 | $0.70 |
| 1,000 | $16 | $7 |
| 10,000 | $160 | $70 |

Caveats: the planned input-validation step adds one short model call per human message, and real games with human players make fewer AI calls. A **$1 daily cap** buys roughly 60 Mafia games or 140 Out of Place games a day.

### 2.4 Who pays

| Way to pay | How it works | Best for |
| --- | --- | --- |
| **Hard budget cap (recommended)** | A global daily limit. When it's spent, the page says "come back tomorrow". Plus a per-IP daily cap | A public demo |
| **Replay mode** | Pre-recorded games anyone can watch, zero API cost | Visitors who just want to see it |
| **Bring your own key** | Players paste an OpenAI key that stays in their browser. Never log it | Unlimited play at no cost to us |
| **Tip jar or sponsors** | Ko-fi or GitHub Sponsors toward the bill. See the licensing note in section 4 | Optional |
| **Run it locally** | Clone and use your own key. Already works | Developers |

Guardrails regardless of the choice:

- The production key lives in its **own OpenAI project with a hard monthly spend limit** (check the OpenAI dashboard for the current options).
- A **global daily budget** in code, with a kill switch.
- Per-IP and per-room limits.

## 3. What must be built before strangers play

| # | Item | Why | Priority |
| --- | --- | --- | --- |
| 1 | **Input validation for human text** | Typed text currently reaches AI prompts word for word, with only a 400-character cap. Build the intent-extraction step from the design doc, so raw text never reaches an AI | Blocker |
| 2 | **Rate limits that work behind a proxy** | The per-IP limit would see every player as one IP. Read the real client IP from the proxy header, and trust only the platform's header | Blocker |
| 3 | **Unguessable room codes and seat tokens** | Game IDs are 40 bits, and anyone with an ID can watch or drive that game | Blocker |
| 4 | **Global spend cap and kill switch** | An open link can drain the API budget | Blocker |
| 5 | **Production run command, Dockerfile, HTTPS, domain** | There's no production run command yet, and `--reload` must be off | Blocker |
| 6 | **Evict finished and idle games** | Finished games are never removed from memory | High |
| 7 | **Abuse protection** | Captcha on room creation, a moderation check on typed text, mute and report between humans. Check OpenAI's usage policies for a public chat feature | High |
| 8 | **Snapshot rooms after each phase** | A deploy shouldn't kill games in progress | High |
| 9 | **Logging and monitoring** | No secrets, no raw human text kept longer than needed, and an alert when the daily budget is nearly spent | High |
| 10 | **Privacy note** | Say what's stored (games, anonymous tokens) and for how long | Medium |
| 11 | **Dependency hygiene** | The dev-server-only Vite advisories; revisit before deploy | Medium |
| 12 | **Name checks** | Search GitHub and the app stores for "Out of Place" and "Trojan Horse"; verify our 40 locations and 400 role titles against the published Spyfall lists by hand | Medium |

## 4. Licensing and a caveat

*Not legal advice.*

- **Mafia and Out of Place** use our own names, locations and text, and can be hosted.
- **Trojan Horse** isn't built yet. Secret Hitler's rules are CC BY-NC-SA 4.0, which allows adaptation only for non-commercial use, with credit and the same license. Whether a tip jar or sponsorship counts as commercial is a legal question. So either redesign the mechanics until the game stands on its own, or keep monetization off that game. Share-alike terms also conflict with an MIT license for anything derived from it, so keep that game's rules text separate if it's adapted.
- **Credit lines** stay in `docs/design.md` and `CLAUDE.md`.
- **Public chat features** fall under OpenAI's usage policies, so read them before launch.

## 5. Multiplayer (2+ humans, AI fills the rest)

### 5.1 What already exists

- **A server-authoritative engine.** Clients send moves and the referee validates them.
- **Per-player views.** Every player already gets a filtered view, so two humans each get their own.
- **Seats as controllers.** The engine doesn't care whether a seat is played by a human or an AI. Today one seat waits for a human, and multiplayer generalizes that to several.

### 5.2 What to add

| Piece | What it is |
| --- | --- |
| **Rooms** | A 5-letter code from an alphabet without look-alike characters. The host picks the game and seat count, friends join by code or link, and empty seats fill with AI cast members at start |
| **Anonymous identity** | A random token (at least 128 bits) in the browser maps to a seat, so a refresh or dropped connection returns you to the same seat. No accounts |
| **Transport** | Keep **SSE for updates plus POST for moves.** A turn-based chat game doesn't need WebSockets. Switch only if we add live typing indicators |
| **Seat controllers** | `Human(token)` or `AI`. The orchestrator awaits each seat's move with a deadline |
| **Timers and takeover** | Each human turn has a deadline (start at 60 seconds). On timeout the existing default move plays. Later, an AI autopilot plays for disconnected humans until they return |
| **Simultaneous phases** | Votes and night actions wait for all humans at once, or until the timeout |
| **Stale-move protection** | Each move carries the turn ID it answers. A repeated or late move gets a 409 and changes nothing |
| **Private channels** | Two human mafia need a private chat. The engine already has channels, so this is mostly UI |
| **Persistence** | Snapshot each room after every phase |
| **Abuse protection** | Rate limits on create and join, message caps, and the input-validation step |

### 5.3 Room lifecycle

`lobby` → `playing` → `finished` → `closed`.

- Lobby rooms close after 30 minutes idle, finished rooms after 10 minutes.
- If the host leaves the lobby, the next human becomes host. If none is left, the room closes.
- Joining after the game starts is refused, with a clear message.

### 5.4 Decisions still open

1. **Can players tell humans from AIs?** Hiding it is more fun but needs human-paced AI messages. Default for now: no "bot" badge during play, and the results screen reveals who was human.
2. **What happens when many humans leave?** AI autopilot fills the seat, or the game ends.
3. **Public matchmaking?** Private room codes first. Matchmaking brings empty lobbies and moderation work.
4. **Human-to-human chat.** Does it go through the same intent pipeline as text sent to AIs?

### 5.5 Hosting for multiplayer

- One container, one process. Each room is light because the work is mostly waiting on the OpenAI API. Measure concurrency with a load test before assuming a number.
- Don't scale out yet. Multiple instances would need sticky routing by room or shared state in Redis.

### 5.6 Testing

- Scripted clients (simulated humans) with the fake model: connect, join, play to the end.
- Chaos cases: disconnect and reconnect, a timeout, a repeated move, two humans moving at the same instant, a stale move after the phase changed, a wrong token, joining after the start.
- A privacy test for several humans: nobody's payloads contain another seat's secret.
- Two browser tabs, and a mobile layout check, on the manual checklist.

## 6. Order of execution

| Step | What | Gate to move on |
| --- | --- | --- |
| **0** | Public repo: rename, audit, README | Clean-clone test passes |
| **1** | Rooms, seats, seat controllers, lobby, and Out of Place playable by 2+ humans in two tabs (timeout plays the default move) | A full game finishes with 2 humans and AIs, and the privacy test passes |
| **2** | Robustness: reconnect, AI autopilot, stale and double moves, idle cleanup | Chaos tests pass |
| **3** | Mafia with several humans: private mafia chat, simultaneous night actions | Full Mafia games with 2 humans |
| **4** | Safety and persistence: input validation, rate limits behind a proxy, caps, snapshots | Section 3 blockers are closed |
| **5** | Deploy readiness: Dockerfile, production command, HTTPS, domain, monitoring | A staging deploy survives a restart |
| **6** | Private beta with friends, behind an invite code and a $1 daily cap | A week of real games without incidents |
| **7** | Public demo: budget cap, replay mode, optional bring-your-own-key | Cost stays under the cap for two weeks |
| **8** | The story: demo video, a post on the balancing method (root-cause diagnosis, noise-aware sample sizes, the roles-hidden finding), portfolio entry | Published |
