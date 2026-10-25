import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { rolesInPlay, type Seat } from "../../game/model";
import type { Status } from "../../types";
import styles from "./ActionDock.module.css";

type Intent = "accuse" | "defend" | "ask" | "claim";

const INTENTS: { id: Intent; label: string; icon: React.ReactNode }[] = [
  {
    id: "accuse",
    label: "Accuse",
    icon: <path d="M4 20L20 4M14 4h6v6" stroke="var(--coral)" strokeLinecap="round" />,
  },
  {
    id: "defend",
    label: "Defend",
    icon: <path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z" stroke="var(--teal)" strokeLinejoin="round" />,
  },
  {
    id: "ask",
    label: "Ask",
    icon: <path d="M9 9a3 3 0 1 1 4 2.8c-.7.3-1 1-1 1.7V15M12 19h.01" stroke="var(--lantern)" strokeLinecap="round" />,
  },
  {
    id: "claim",
    label: "Claim role",
    icon: (
      <>
        <rect x="5" y="3" width="14" height="18" rx="2" stroke="var(--lavender)" />
        <path d="M9 8h6M9 12h6" stroke="var(--lavender)" />
      </>
    ),
  },
];

const TEMPLATE: Record<Intent, (target: string) => string> = {
  accuse: (n) => `i think ${n.toLowerCase()} is mafia. `,
  defend: (n) => `i don't think it's ${n.toLowerCase()}. `,
  ask: (n) => `${n.toLowerCase()}, why `,
  claim: (role) => `i'm the ${role}. `,
};

/** Quick intents (each opens a target picker and drafts a line you can edit), a free-text box,
 * and the controls that move the chat along: Speak up, Next, Pass. */
export function ActionDock({ status, seats, nextName, busy, onSay, onNext, onPass, error }: {
  status: Status;
  busy: boolean; // someone is mid-message
  seats: Seat[];
  nextName: string | null;
  onSay: (text: string, accuses: string | null) => Promise<boolean>;
  onNext: () => void;
  onPass: () => void;
  error: string;
}) {
  const [text, setText] = useState("");
  const [picking, setPicking] = useState<Intent | null>(null);
  const [accusing, setAccusing] = useState<string | null>(null); // the public "you → them" chip
  const input = useRef<HTMLInputElement>(null);
  const discussion = status.phase === "discussion";
  const yourTurn = discussion && status.waiting_on_you;
  const canNext = discussion && status.waiting_for_next && !busy && !text.trim();
  const others = seats.filter((s) => s.alive && !s.you);

  useEffect(() => {
    if (yourTurn) input.current?.focus();
  }, [yourTurn]);

  const draft = (intent: Intent, target: string, pid: string | null = null) => {
    setText(TEMPLATE[intent](target));
    setAccusing(intent === "accuse" ? pid : null);
    setPicking(null);
    requestAnimationFrame(() => input.current?.focus());
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim()) {
      if (await onSay(text.trim(), accusing && others.some((s) => s.id === accusing) ? accusing : null)) {
        setText("");
        setAccusing(null);
      }
    } else if (canNext) onNext();
  };

  return (
    <form className={`${styles.dock} ${yourTurn ? styles.yourTurn : ""}`} onSubmit={submit}>
      {yourTurn && <p className={styles.turnNote}>Your turn. The table is waiting on you.</p>}
      <div className={styles.intents}>
        {INTENTS.map((i) => (
          <button key={i.id} type="button" disabled={!discussion}
                  className={`${styles.intent} ${picking === i.id ? styles.intentOpen : ""}`}
                  aria-expanded={picking === i.id} onClick={() => setPicking(picking === i.id ? null : i.id)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" strokeWidth="2.6" aria-hidden="true">{i.icon}</svg>
            {i.label}
          </button>
        ))}
      </div>
      {picking && (
        <div className={styles.picker} role="dialog" aria-label={`${picking}: pick`}>
          <span className={styles.pickerTitle}>
            {picking === "claim" ? "Claim which role?" : picking === "ask" ? "Ask whom?" : `${picking[0].toUpperCase()}${picking.slice(1)} whom?`}
          </span>
          <div className={styles.targets}>
            {picking === "claim"
              ? rolesInPlay(status).map((r) => (
                  <button key={r} type="button" className={`${styles.target} ${styles.roleTarget}`} onClick={() => draft("claim", r)}>
                    {r}
                  </button>
                ))
              : others.map((s) => (
                  <button key={s.id} type="button" className={styles.target} onClick={() => draft(picking, s.name, s.id)}>
                    {s.character && <Portrait character={s.character} size={36} />}
                    {s.name}
                  </button>
                ))}
          </div>
        </div>
      )}
      {accusing && (
        <div className={styles.accusing}>
          <span>Accusing <strong>{seats.find((s) => s.id === accusing)?.name}</strong>: the table will see you → them</span>
          <button type="button" className={styles.clear} aria-label="Don't accuse anyone" onClick={() => setAccusing(null)}>✕</button>
        </div>
      )}
      <div className={styles.row}>
        <label htmlFor="say" className="visually-hidden">Say something</label>
        <input
          id="say"
          ref={input}
          className={styles.input}
          value={text}
          maxLength={400}
          disabled={!discussion}
          autoComplete="off"
          placeholder={
            !discussion
              ? status.phase === "vote" ? "The vote is open…" : "The town sleeps…"
              : canNext ? "Jump in, or press Enter for the next voice…" : "Say something to the table…"
          }
          onChange={(e) => setText(e.target.value)}
        />
        {canNext ? (
          <Button variant="surface" type="submit">Next{nextName ? `: ${nextName}` : ""} ▸</Button>
        ) : (
          <Button variant="lantern" type="submit" disabled={!discussion || !text.trim()}>Speak up</Button>
        )}
        {yourTurn && <Button variant="ghost" onClick={onPass}>Pass</Button>}
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
    </form>
  );
}

/** Out of the game: watch, and keep the chat moving. */
export function SpectatorDock({ canNext, nextName, onNext }: { canNext: boolean; nextName: string | null; onNext: () => void }) {
  return (
    <div className={`${styles.dock} ${styles.spectator}`}>
      <span className={styles.muted}>You're out. Watch how it ends.</span>
      {canNext && <Button variant="surface" onClick={onNext}>Next{nextName ? `: ${nextName}` : ""} ▸</Button>}
    </div>
  );
}
