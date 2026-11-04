import { useState } from "react";
import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { CUES, type Mark, type Marks } from "../../game/marks";
import { usePersisted } from "../../persisted";
import { ROLE_COLOR, type Seat } from "../../game/model";
import type { GameEvent, Status } from "../../types";
import { ReadPopover } from "./TableStrip";
import styles from "./Notes.module.css";

/** Your notes for one game, kept in the browser, plus the chat lines you pinned (★ toggles a pin). */
export function useNotes(gameId: string) {
  const [notes, setNotes] = usePersisted(`kira:${gameId}:notes`, "");
  const [pinned, setPinned] = usePersisted<number[]>(`kira:${gameId}:pinned`, []);
  const pin = (e: GameEvent, _who?: string) =>
    setPinned(pinned.includes(e.seq) ? pinned.filter((s) => s !== e.seq) : [...pinned, e.seq]);
  return { notes, setNotes, pinned, pin };
}

/** The player's corner of the live table: Pause / Continue and Call the vote, your secret, and your notes
 * (reads on each player, pinned lines, a scratchpad), folded away until you want them. */
export function ControlCenter({ paused, onPause, canCallVote, onCallVote, open, onOpen, status, seats, events,
  notes, onNotes, pinned, onPin, marks, guesses, onMark }: {
  paused: boolean;
  onPause: () => void;
  canCallVote: boolean;
  onCallVote: () => void;
  open: boolean;
  onOpen: (open: boolean) => void;
  status: Status;
  seats: Seat[];
  events: GameEvent[];
  notes: string;
  onNotes: (text: string) => void;
  pinned: number[];
  onPin: (e: GameEvent) => void;
  marks: Marks;
  guesses: string[];
  onMark: (pid: string, m: Mark) => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const others = seats.filter((s) => !s.you);
  const pins = events.filter((e) => e.kind === "say" && pinned.includes(e.seq));
  const nameOf = (pid: string | null) => {
    const s = seats.find((x) => x.id === pid);
    return s ? (s.you ? "You" : s.name) : "?";
  };
  const reads = others.filter((s) => {
    const m = marks[s.id];
    return m && (m.cue || m.role || m.note);
  }).length;
  const count = reads + pins.length + (notes.trim() ? 1 : 0);

  return (
    <aside className={styles.center} aria-label="Your controls, notes and secret">
      <div className={styles.controls}>
        <Button variant="lantern" size="large" block onClick={onPause} aria-pressed={paused}
                className={paused ? styles.pausedBtn : undefined}>
          {paused ? "▶  Continue" : "❚❚  Pause"}
        </Button>
        <Button variant="coral" block onClick={onCallVote} disabled={!canCallVote}>Call the vote</Button>
        <span className={`meta ${styles.hint}`}>{paused ? "The table waits for you" : "Space pauses the talk"}</span>
      </div>
      <SecretCard status={status} seats={seats} events={events} />
      <section className={styles.notesBox}>
        <button type="button" className={styles.notesToggle} aria-expanded={open} onClick={() => onOpen(!open)}>
          <span className={styles.title}>Notes</span>
          {count > 0 && <span className={styles.badge}>{count}</span>}
          <span className={styles.chev} aria-hidden="true">{open ? "▾" : "▸"}</span>
        </button>
        {open && (
          <div className={styles.notesBody}>
            <span className={`meta ${styles.sub}`}>Your reads</span>
            <ul className={styles.reads}>
              {others.map((s) => {
                const m = marks[s.id] ?? {};
                const cue = CUES.find((c) => c.id === m.cue);
                return (
                  <li key={s.id} className={s.alive ? undefined : styles.gone}>
                    <button type="button" className={styles.read} aria-expanded={editing === s.id}
                            onClick={() => setEditing(editing === s.id ? null : s.id)}>
                      {s.character && <Portrait character={s.character} size={30} mood={s.alive ? "neutral" : "dead"} />}
                      <strong className={styles.readName}>{s.name}</strong>
                      <span className={styles.readText}>
                        {cue && <span style={{ color: cue.color }}>{cue.label}</span>}
                        {m.role && <span>{m.role}?</span>}
                        {m.note && <span className={styles.readNote}>{m.note}</span>}
                        {!cue && !m.role && !m.note && <span className={styles.none}>no read yet</span>}
                      </span>
                    </button>
                    {editing === s.id && (
                      <ReadPopover inline seat={s} mark={m} guesses={guesses} onMark={(next) => onMark(s.id, next)}
                                   onClose={() => setEditing(null)} />
                    )}
                  </li>
                );
              })}
            </ul>
            <span className={`meta ${styles.sub}`}>Pinned lines</span>
            {pins.length === 0 ? (
              <p className={styles.none}>Pin a chat line with ★ to keep it here.</p>
            ) : (
              <ul className={styles.pins}>
                {pins.map((e) => (
                  <li key={e.seq} className={styles.pinRow}>
                    <p className={styles.pinText}>
                      <span className="meta">Day {e.day}</span> <strong>{nameOf(e.actor)}</strong> {e.text}
                    </p>
                    <button type="button" className={styles.unpin} aria-label="Unpin" onClick={() => onPin(e)}>✕</button>
                  </li>
                ))}
              </ul>
            )}
            <label htmlFor="notes" className={`meta ${styles.sub}`}>Scratchpad</label>
            <textarea id="notes" className={`${styles.notes} ${styles.scratch}`} value={notes} spellCheck={false} rows={3}
                      placeholder="who claimed what, who voted with who…" onChange={(e) => onNotes(e.target.value)} />
          </div>
        )}
      </section>
    </aside>
  );
}

/** Always-open notes, with your secret role underneath. */
export function NotesPanel({ notes, onNotes, status, seats, events }: {
  notes: string;
  onNotes: (text: string) => void;
  status: Status;
  seats: Seat[];
  events: GameEvent[];
}) {
  return (
    <aside className={styles.panel} aria-label="Your notes and your secret">
      <label htmlFor="notes" className={styles.title}>Notes</label>
      <textarea id="notes" className={styles.notes} value={notes} spellCheck={false}
                placeholder={"who claimed what, who voted with who…\npin a chat line with ★"}
                onChange={(e) => onNotes(e.target.value)} />
      <SecretCard status={status} seats={seats} events={events} />
    </aside>
  );
}

function SecretCard({ status, seats, events }: { status: Status; seats: Seat[]; events: GameEvent[] }) {
  const mine = events.filter((e) => e.vis === `private:${status.you}` || e.vis.startsWith("channel:"));
  const teammates = status.teammates.map((t) => seats.find((s) => s.id === t)?.name).filter(Boolean);
  let detail = "";
  if (status.role === "mafia") {
    const choice = [...mine].reverse().find((e) => e.kind === "mafia_choice");
    detail = `${teammates.length ? `Your partner: ${teammates.join(", ")}.` : "You work alone."}${choice ? ` ${choice.text}` : ""}`;
  } else if (status.role === "detective") {
    const results = mine.filter((e) => e.kind === "result").map((e) => e.text.replace(/^Your investigation: /, ""));
    detail = results.length ? results.join(" ") : "Nobody investigated yet.";
  } else if (status.role === "doctor" || status.role === "bodyguard") {
    const last = [...mine].reverse().find((e) => e.kind === "result");
    detail = last ? last.text : status.role === "doctor" ? "Nobody protected yet." : "Nobody guarded yet.";
  } else if (status.role === "jester") {
    detail = "You win only if the town votes you out. Look guilty, but not too guilty.";
  } else {
    detail = "No powers. Just your wits.";
  }
  return (
    <div className={styles.secret}>
      <span className={`meta ${styles.secretLabel}`}>Your secret</span>
      <p className={styles.secretText}>
        You're the <strong style={{ color: ROLE_COLOR[status.role] }}>{status.role}</strong>. {detail}
      </p>
    </div>
  );
}
