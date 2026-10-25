import { usePersisted } from "../../persisted";
import { ROLE_COLOR, type Seat } from "../../game/model";
import type { GameEvent, Status } from "../../types";
import styles from "./Notes.module.css";

/** Your notes for one game, kept in the browser, plus the chat lines you pinned into them. */
export function useNotes(gameId: string) {
  const [notes, setNotes] = usePersisted(`kira:${gameId}:notes`, "");
  const [pinned, setPinned] = usePersisted<number[]>(`kira:${gameId}:pinned`, []);
  const pin = (e: GameEvent, who: string) => {
    if (pinned.includes(e.seq)) {
      setPinned(pinned.filter((s) => s !== e.seq));
      return;
    }
    setPinned([...pinned, e.seq]);
    const entry = `★ day ${e.day} · ${who}: ${e.text}\n`;
    setNotes(notes ? `${notes.replace(/\n*$/, "")}\n${entry}` : entry);
  };
  return { notes, setNotes, pinned, pin };
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
