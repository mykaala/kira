import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import type { Marks } from "../../game/marks";
import { nameOf, type SpySeat } from "../../spy/seats";
import { RULE_LABEL, type SpyReveal, type SpyStatus } from "../../spy/types";
import styles from "../results/Results.module.css";
import own from "./SpyResults.module.css";
import { SpyLog } from "./SpyLog";

const TILTS = [-2, 1.5, -1, 2, -1.5, 1, -2, 1.5];

/** The outcome, the place, who the spy was, how it ended, everyone's card with their voice, and the log. */
export function SpyResults({ status, seats, reveal, marks, onReview, onRematch, onSettings, onExit }: {
  status: SpyStatus;
  seats: SpySeat[];
  reveal: SpyReveal;
  marks: Marks;
  onReview: () => void;
  onRematch: () => void;
  onSettings: () => void;
  onExit: () => void;
}) {
  const winner = reveal.winner;
  const headline = reveal.ended && !winner
    ? "No result."
    : (reveal.end_text ?? "").split(/(?<=[.!])\s/)[0] || "Game over.";
  const youWon = winner === "draw" ? null : winner === (status.role === "spy" ? "spy" : "civilians");
  const spyName = reveal.spy === status.you ? "You were the spy." : `${nameOf(seats, reveal.spy)} was the spy.`;
  const outIn = Object.fromEntries(reveal.rounds.filter((r) => r.out).map((r) => [r.out!, r.round]));
  const tally = (votes: Record<string, number>) =>
    Object.entries(votes).sort((a, b) => b[1] - a[1]).map(([pid, n]) => `${nameOf(seats, pid)} ${n}`).join(", ");

  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <section className={`${styles.banner} ${youWon === false ? styles.dusk : ""}`}>
          <div className={styles.bannerText}>
            <span className={styles.kicker}>The place: {reveal.place}</span>
            <h1 className={styles.headline}>{headline}</h1>
            <p className={own.sub}>
              {spyName}{" "}
              {youWon === true ? "You won." : youWon === false ? "You lost." : winner === "draw" ? "Nobody wins this one." : ""}
            </p>
          </div>
          <div className={styles.bannerActions}>
            <Button variant="dark" onClick={onRematch}>Play again</Button>
            <Button variant="ghost" className={styles.outline} onClick={onSettings}>Change settings</Button>
            <Button variant="ghost" className={styles.outline} onClick={onExit}>All games</Button>
          </div>
        </section>

        <section className={own.how} aria-label="How it ended">
          <h2 className={styles.h2}>How it ended</h2>
          {reveal.ended && <p className={own.line}>{reveal.ended}.</p>}
          {reveal.rounds.map((r) => {
            const label = reveal.rounds.length > 1 ? `Round ${r.round} ` : "";
            return (
              <p key={r.round} className={own.line}>
                <strong>{label}{label ? "vote" : "Vote"}:</strong> {tally(r.votes)}
                {Object.keys(r.revotes).length > 0 && <>; <strong>revote:</strong> {tally(r.revotes)}</>}
                {r.out && <> · {nameOf(seats, r.out)} {r.out === status.you ? "were" : "was"} voted out</>}
              </p>
            );
          })}
          {reveal.guesses.map((g, i) => (
            <p key={i} className={own.line}>
              <strong>{g.kind === "last_guess" ? "Last chance" : "The spy named the place"}:</strong> “{g.guess}”,{" "}
              <span className={g.match ? own.right : own.wrong}>{g.match ? "right" : "wrong"}</span>{" "}
              <span className={own.rule}>({RULE_LABEL[g.rule] ?? g.rule}{g.rule.startsWith("judge") ? `: ${g.reason}` : ""})</span>
            </p>
          ))}
          {status.notices.length > 0 && (
            <ul className={own.notices}>{status.notices.map((n) => <li key={n}>{n}</li>)}</ul>
          )}
          <button type="button" className={styles.replay} onClick={onReview}>Replay the whole game →</button>
        </section>

        <section aria-label="Cards on the table" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <h2 className={styles.h2}>Cards on the table</h2>
          <div className={styles.cards}>
            {seats.map((s, i) => {
              const role = reveal.roles[s.id];
              const read = marks[s.id]?.cue;
              return (
                <article key={s.id} className={`${styles.card} ${s.you ? styles.youCard : ""}`} tabIndex={0}
                         aria-label={`${s.you ? "You" : s.name}: ${role}${reveal.voices[s.id] ? `, ${reveal.voices[s.id]}` : ""}`}
                         style={{ "--tilt": `${TILTS[i % TILTS.length]}deg`, "--delay": `${i * 110}ms`,
                                  background: role === "spy" ? "var(--coral)" : "var(--teal)" } as React.CSSProperties}>
                  {s.character ? (
                    <div className={styles.art}>
                      <Portrait character={s.character} mood={role === "spy" ? "smug" : "neutral"} size="fill" shape="square" />
                    </div>
                  ) : (
                    <div className={styles.youArt}>You</div>
                  )}
                  <div className={styles.cardBody}>
                    <strong className={styles.cardName}>{s.you ? "You" : s.name}</strong>
                    <span className={styles.cardRole}>{role}</span>
                    {reveal.place_roles?.[s.id] && <span className={styles.cardFate}>{reveal.place_roles[s.id]}</span>}
                    {reveal.voices[s.id] && <span className={styles.cardFate}>{reveal.voices[s.id]}</span>}
                    {outIn[s.id] && <span className={styles.cardFate}>voted out in round {outIn[s.id]}</span>}
                    {read && !s.you && <span className={styles.cardFate}>your read: {read === "mafia" ? "spy!" : read}</span>}
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <SpyLog seats={seats} events={reveal.events} title="Every question" />
      </div>
    </div>
  );
}
