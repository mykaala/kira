import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import type { Character, CharacterId } from "../../cast";
import { CUES, type Marks } from "../../game/marks";
import type { Seat } from "../../game/model";
import { summarize, type Fate } from "../../game/results";
import type { GameEvent, Status } from "../../types";
import styles from "./Results.module.css";

const ROLE_FILL: Record<string, string> = {
  mafia: "var(--coral)",
  detective: "var(--lavender)",
  doctor: "var(--teal)",
  villager: "var(--text)",
  jester: "var(--pink)",
  bodyguard: "var(--sky)",
};
const TILTS = [-2, 1.5, -1, 2, -1.5, 1, -2, 1.5, -0.5];

/** The sunrise (or not), everyone's card flipped face up, the turning point and your stickers. */
export function Results({ status, seats, events, cast, marks, onReview, onRematch, onExit }: {
  status: Status;
  seats: Seat[];
  events: GameEvent[];
  cast: Partial<Record<CharacterId, Character>>;
  marks: Marks;
  onReview: () => void;
  onRematch: () => void;
  onExit: () => void;
}) {
  const s = summarize(status, seats, events);
  const town = status.winner === "village";
  const lastWords = (pid: string) => [...events].reverse().find((e) => e.kind === "say" && e.actor === pid)?.text;
  const mvpSeat = seats.find((x) => x.id === s.mvp);

  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <section className={`${styles.banner} ${town ? "" : styles.dusk}`}>
          <svg className={styles.scene} viewBox="0 0 1200 260" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
            <circle cx="960" cy="250" r="150" fill={town ? "#FFD08A" : "#FFB547"} />
            <path
              d="M0 260 V200 L80 160 L160 200 V260Z M140 260 V180 L220 130 L300 180 V260Z M720 260 V190 L800 150 L880 190 V260Z M1040 260 V170 L1120 130 L1200 170 V260Z"
              fill={town ? "#E08A4F" : "#C9553C"}
            />
          </svg>
          <div className={styles.bannerText}>
            <span className={styles.kicker}>{s.kicker}</span>
            <h1 className={styles.headline}>{s.headline}</h1>
          </div>
          <div className={styles.bannerActions}>
            <Button variant="dark" onClick={onRematch}>Rematch</Button>
            <Button variant="ghost" className={styles.outline} onClick={onExit}>New game</Button>
          </div>
        </section>

        <section aria-label="Role reveal" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className={styles.sectionHead}>
            <h2 className={styles.h2}>Cards on the table</h2>
            <span className={styles.hint}>Hover a card to hear their last words</span>
          </div>
          <div className={styles.cards}>
            {seats.map((seat, i) => (
              <RoleCard key={seat.id} seat={seat} fate={s.fates[seat.id] ?? null} mvp={seat.id === s.mvp}
                        tilt={TILTS[i % TILTS.length]} delay={i * 110} lastWords={lastWords(seat.id)}
                        guess={marks[seat.id]} />
            ))}
          </div>
        </section>

        <div className={styles.bottom}>
          <section className={styles.turning} aria-label="The turning point">
            {mvpSeat?.character && (
              <Portrait character={mvpSeat.character} mood="smug" size={96} shape="rounded" className={styles.turningPortrait} />
            )}
            <div className={styles.turningText}>
              <span className={`meta ${styles.turningKicker}`}>
                The turning point · Day {s.quote?.day ?? status.day}
                {mvpSeat?.character && cast[mvpSeat.character] ? ` · ${mvpSeat.name}, ${cast[mvpSeat.character]!.voice.toLowerCase()}` : ""}
              </span>
              <p className={styles.quote}>
                {s.quote ? `“${s.quote.text}”` : "Nobody said a word that mattered. Strange night."}
              </p>
            </div>
          </section>
          <section className={styles.stickers} aria-label="Stickers earned">
            <h3 className={styles.h3}>Stickers earned</h3>
            <div className={styles.stickerRow}>
              {s.stickers.length === 0 && <span className={styles.hint}>None this time.</span>}
              {s.stickers.map((st, i) => (
                <span key={st.label} className={styles.sticker}
                      style={{ "--s": st.color, transform: `rotate(${i % 2 ? 2 : -2}deg)` } as React.CSSProperties}>
                  {st.label}
                </span>
              ))}
            </div>
            <button type="button" className={styles.replay} onClick={onReview}>Replay the whole game →</button>
          </section>
        </div>
      </div>
    </div>
  );
}

function RoleCard({ seat, fate, mvp, tilt, delay, lastWords, guess }: {
  seat: Seat;
  fate: Fate;
  mvp: boolean;
  tilt: number;
  delay: number;
  lastWords?: string;
  guess?: Marks[string];
}) {
  const role = seat.role ?? "villager";
  const dead = !seat.alive;
  const read = guess?.cue ? CUES.find((c) => c.id === guess.cue)?.label : null;
  const fateText = fate ? `${fate.how === "killed" ? "killed N" : "voted D"}${fate.day}` : null;
  const cls = [styles.card, dead && styles.dead, seat.you && styles.youCard].filter(Boolean).join(" ");
  return (
    <article
      className={cls}
      tabIndex={0}
      aria-label={`${seat.you ? "You" : seat.name}: ${role}${fateText ? `, ${fateText}` : ""}`}
      style={{ "--tilt": `${tilt}deg`, "--delay": `${delay}ms`, background: dead ? "#B8ADCB" : ROLE_FILL[role] } as React.CSSProperties}
    >
      {mvp && <span className={styles.mvp}>MVP</span>}
      {lastWords && <span className={styles.lastWords}>“{lastWords}”</span>}
      {seat.character ? (
        <div className={styles.art}>
          <Portrait character={seat.character} mood={dead ? "dead" : role === "mafia" ? "angry" : "neutral"} size="fill" shape="square" />
        </div>
      ) : (
        <div className={styles.youArt}>You</div>
      )}
      <div className={styles.cardBody}>
        <strong className={styles.cardName}>{seat.you ? "You" : seat.name}</strong>
        <span className={styles.cardRole}>{role}{fateText ? ` · ${fateText}` : ""}</span>
        {(read || guess?.role) && !seat.you && (
          <span className={styles.cardFate}>
            your read: {[read, guess?.role && `${guess.role}?`].filter(Boolean).join(", ")}
          </span>
        )}
      </div>
    </article>
  );
}
