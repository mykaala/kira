# Kira — UI spec (Direction B: "Lantern Hour")

Single-player social deduction (Mafia, Out of Place, and Trojan Horse coming soon) against AI characters.
Mood: a candlelit table at night. Cozy but tense. Hand-made indie game, not a SaaS dashboard.

The reference mockups are in `screens/`. Open them in a browser. They're static HTML with inline styles: treat them as **visual truth**, not as code to copy. Rebuild them as real components.

## 1. Design tokens

```css
:root {
  /* ground & surfaces */
  --bg:          #1D1830;  /* page, deep plum night */
  --surface:     #2A2342;  /* panels, cards */
  --surface-2:   #352C52;  /* chips, buttons, hover */
  --surface-3:   #3A2F5C;  /* stage / featured panel */
  --line:        #4A3F6E;  /* borders, dividers */
  --shadow:      #0E0B19;  /* hard offset shadow colour */

  /* text */
  --text:        #F4EBDD;  /* cream */
  --text-soft:   #D8CFE3;  /* body copy on surfaces */
  --muted:       #B8ADCB;  /* labels, meta */
  --dead:        #8C82A3;  /* eliminated players */

  /* accents */
  --lantern:     #FFB547;  /* primary CTA, timer, "you" */
  --coral:       #FF7A59;  /* accusation, Mafia, danger */
  --coral-text:  #FF9A80;  /* coral used as small text on dark */
  --teal:        #5CC8B8;  /* Doctor / protection / positive */
  --lavender:    #9B8BD9;  /* Detective */

  /* shape */
  --r-sm: 8px; --r-md: 14px; --r-lg: 22px; --r-xl: 28px; --r-pill: 999px;
  --shadow-hard: 4px 4px 0 var(--shadow);   /* buttons */
  --shadow-card: 8px 8px 0 var(--shadow);   /* cards, stage */
}
```

Text on `--lantern`, `--coral` or `--teal` fills is always `--bg` (#1D1830), never white.

Background texture: a faint dot grid, `radial-gradient(rgba(244,235,221,.07) 1px, transparent 1.5px)` at `28px 28px`.

## 2. Typography (Google Fonts)

| Role | Family | Use |
|---|---|---|
| Display | **Bricolage Grotesque** 700/800, `letter-spacing:-0.02 to -0.035em` | Titles, names, speech bubbles, buttons |
| Body | **Atkinson Hyperlegible** 400/700 | Dialogue log, descriptions, inputs |
| Meta | **Space Mono** 400/700, uppercase, `letter-spacing:.08–.12em` | Phase labels, timers, chips, counts |

Scale: hero 84 / page title 60 / card title 40 / section 24–30 / speech 30 / body 17 / small 15 / meta 12–13.

## 3. Signature details (what makes it feel like this direction)

- **Hard offset shadows**, never blurred. On hover, a button or card moves `translate(-2px,-2px)` and its shadow grows (4→6px, 8→10px).
- **Chunky radii** (14–28px) and 3px borders on featured cards.
- The **lantern** logo mark and the **candle-burn timer** (a cream wax bar with a flickering flame at its edge).
- **Character faces** are flat SVG: a coloured backdrop, a head, a hair silhouette, and eyes, brows and mouth as strokes. Expression lives in the brows and mouth. Each character has one signature colour, used for their backdrop and their dot in the log.
- Little **physical touches**: role cards on the results screen sit at slight random rotations (±2°), and award "stickers" are tilted pills.

## 4. The cast (consistent across all games)

| Character | Archetype | Backdrop colour | Visual cue |
|---|---|---|---|
| Ines Varga | The Analyst | `#5CC8B8` | bun, round glasses |
| Bram Holt | The Hothead | `#FF7A59` | blue flat cap, ginger beard, angry brows |
| Odile Fenn | The Quiet One | `#9B8BD9` | long black hair, half-lidded eyes |
| Tobiah Reyes | The Charmer | `#FFB547` | swept hair, raised brow, big smile |
| Kit Amari | The Wildcard | `#E86FA8` | spiky green hair, wink, crooked grin |
| Marguerite Sol | The Elder | `#8FB573` | white curls, closed smiling eyes |
| Juno Park | The Peacemaker | `#6FA8E8` | coral beret |
| Hollis Wren | The Skeptic | `#B8ADCB` | square glasses, grey hair |

Build a `<Portrait character="bram" mood="angry|neutral|smug|speaking|dead" size={…} />` component. The SVG paths are in the mockups and can be lifted from there. Moods change only brows, eyes and mouth. `dead` desaturates the portrait and uses X eyes.

Each character also carries traits (talkative, suspicious, good liar, each 0–1). The lobby's "Up close" panel shows these as bars.

## 5. Screens

### 01 Game select
Header (logo, nav, settings) → hero line "Who's lying tonight?" → three game cards in an auto-fit grid (`minmax(300px,1fr)`) → a "continue unfinished game" strip.
Each card has an illustrated scene, the title, a one-line pitch, chips (seats, minutes, bluff level) and a CTA. The selected or featured card gets a lantern-coloured border and a lantern CTA. The others use a `--surface-2` CTA.

Each card ends in two buttons: a square **Info** (ⓘ) and the wide **Play** (the game's own label plus an arrow icon). Hovering or keyboard-focusing Info swaps their widths (flex-grow, about 0.3s): Info reads "How to Play" and Play shrinks to its arrow. Touch never hovers, so a tap on Info just opens the page. A game that isn't playable shows an hourglass instead of the arrow.

### How to Play (`#/how/<game>`)
One page per game, about 150 words: hero (title, one-line goal, the card's art), then six numbered sections: **Who's at the table** (tilted role cards), **How a round goes** (3–4 numbered steps), **How it ends** (win cards), **Table tips** (three), **Watch** (a looping captioned scene acted by the cast with portrait moods, bubbles, tags and vote dots; it starts in view, can be paused and stepped, and Out of Place adds an "As a civilian / As the spy" toggle), and **Your turn** (a one-question quiz). It ends with the Play button. A game that isn't playable gets a short teaser instead. Rules text follows the engine's defaults; keep it in step with `backend/src/engine/modes`.

### 02 Lobby / opponent selection
Left: a **round table**. Seats are placed in a circle (as % positions around the centre), and the centre shows the "2 among 8 / Mafia hiding" count. "You" is a dashed lantern-coloured seat at the bottom. Clicking a seat selects it.
Every AI seat always shows its character; a new table is dealt at random. The page fits one screen from 900×640 up: the table takes the height left over (`--fit` on `RoundTable`), and seats scale with it. The table's middle (`RoundTable`'s `center` slot) shows the count and **Redraw**; with a seat picked it shows "Swap Kit for…", the waiting faces, **Empty seat** and **Keep**. New faces pop into their seat.
Right: one **House rules** card (name; AI players stepper beside a "Tricky · tune ↗" link to the Characters page; a 2×2 grid of role pills, Doctor and Detective fixed with a ✓, Jester and Bodyguard as switches, and one hint line), then the CTA "Blow out the lantern", the column centred vertically. No knobs in the lobby, and no seat count in the header.

Every lobby is built from `screens/lobby/LobbyParts.tsx` (`LobbyFrame`, `SeatTable`, `Stepper`, `SwitchPills`). Out of Place: the same frame and table ("1 among 6 / spy hiding"); its card has name, players (you included), your role (Random / Civilian / Spy) and **Extras** as switch pills (Place roles, Angles).

### Characters
A one-row **How sharp are they?** card: the heading beside three compact choices (Cozy / Tricky / Merciless), each with a few words on what it means. Below it, each character's card has their three knobs as sliders. A hand-set card gets a lantern outline, "Set by hand", and **Reset to <difficulty>**; **Reset all** appears when any are hand-set.

### 03 Live discussion (the most important screen)
The whole screen fits one viewport on desktop: only the chat and the notes scroll inside. Layout from top to bottom:
1. **Phase bar**: "Day 2", the candle timer and the time left. Nothing else.
2. **Table strip**: every living player as a compact chip (portrait, name, status line). The speaker's chip is filled lantern and pulses with typing dots while they talk. Status lines show live vote intent (`→ Kit`) in coral text. Whoever the newest line names reacts in a small thought bubble over their chip ("scoffs loudly"), capped at three, gone in about 4 s. Click a chip for your read on them (the popover flips left at the screen edge). Eliminated players sit at the end as dimmed initials.
3. **Banner** (main column, only when it matters): the morning's news before anyone speaks, the night (or your night pick), and the vote tray with its verdict. During the talk there is no banner.
4. **The chat** (main column, fills what's left): the compact transcript with day dividers, and the **live line** highlighted at the bottom: portrait, name, "replying to X" pill, larger text typing out. Lines can be pinned with ★.
5. **Action dock**: quick intents (Accuse / Defend / Ask / Claim role, discussion only) plus a free-text input, "Speak up" and, on your turn, "Pass".
6. **Control center** (side column): a big **Pause / Continue** (Space toggles it) and **Call the vote** under it, your secret role, then **Notes**, folded by default with a count badge: your reads on each player (the same cue / role / note as the chip popover), pinned lines as a list you can unpin, and a small scratchpad.

Pacing: the talk moves on by itself, no Next button. Each finished line stays the newest for at least 3.5 s (more for long lines, plus up to 1 s of jitter) before the next starts. The browser asks the server for each next speaker, so it is never more than one line ahead of what you've read, and Pause stops the talk within a line.

Anti-clutter rules: only one line is ever large. Reactions are capped at three and fade out.

Vote phase: the banner becomes a vote tray of portraits. Choosing one locks your vote, and the other players' votes land one at a time with a short delay for tension.

### 04 Results & role reveal
A sunrise banner in warm orange with the outcome headline, plus Rematch and New game buttons → **"Cards on the table"**: a role card for everyone, flipped (the reveal can animate as a staggered card flip). Mafia cards are coral, the Detective lavender, the Doctor teal, villagers cream, and eliminated players dimmed with X eyes → a "turning point" quote from the MVP → earned stickers → replay link.

## 6. Responsive rules
- Containers are `max-width: 1320–1392px` and centred, with a 24px gutter (16px on phones).
- Multi-column rows use `flex-wrap` with `flex: 999 1 <min>` for the main column so side panels drop below on narrow screens.
- On mobile in the discussion screen, the table strip scrolls horizontally, the page scrolls normally, and the control center drops below the chat.
- Touch targets are at least 44px. Keep visible focus rings using `--lantern`.

## 7. Accessibility
- Use real `<button>`, `<input>` and `<label>` elements. Icon-only buttons get an `aria-label`.
- The timer has `role="timer"`. The streaming speech should be an `aria-live="polite"` region.
- Respect `prefers-reduced-motion`: turn off the flame flicker, typing-dot bounce and card tilt-hover.

## 8. Suggested build
React + TypeScript + Vite. Put the CSS variables above in `tokens.css` (or a Tailwind theme extension). Suggested components: `Portrait`, `Button` (variants: lantern, coral, surface, ghost), `Chip`, `CandleTimer`, `TableStrip`, `SpeechStage`, `ActionDock`, `TranscriptLog`, `RoleCard`, `RoundTable`, `GameCard`.
