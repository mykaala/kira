import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { nameOf, type SpySeat } from "../../spy/seats";
import { MAX_CHARS, MAX_GUESS_WORDS, MAX_WORDS, wordCount, type SpyMove, type SpyStatus } from "../../spy/types";
import styles from "./SpyGame.module.css";

export type MoveResult = { ok: true } | { ok: false; warning?: string; error?: string };

/** The one input area: it adapts to your turn (ask, answer, name the place) with a clear prompt, a word
 * counter and Enter to send. Votes are cast on the stage. Off-turn it shows who you're waiting on. */
export function SpyDock({ status, seats, guess, onGuess, onMove, onNext }: {
  status: SpyStatus;
  seats: SpySeat[];
  guess: string; // shared with the places list in Your secret
  onGuess: (t: string) => void;
  onMove: (m: SpyMove) => Promise<MoveResult>;
  onNext: () => void;
}) {
  const turn = status.turn;
  const [text, setText] = useState("");
  const [target, setTarget] = useState<string | null>(null);
  const [naming, setNaming] = useState(false); // the spy chose to name the place instead of asking
  const [busy, setBusy] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const key = turn ? `${turn.type}:${status.questions}` : "none";

  useEffect(() => {
    setText("");
    setTarget(turn?.targets.length === 1 ? turn.targets[0] : null);
    setNaming(turn?.type === "last_chance");
    setWarning(null);
    setError("");
    if (turn && turn.type !== "vote" && turn.type !== "revote") requestAnimationFrame(() => input.current?.focus());
  }, [key]); // reset only when a new turn starts

  if (!turn || turn.type === "vote" || turn.type === "revote") {
    const waitingOn =
      status.phase === "ask" ? `${nameOf(seats, status.asker)} is asking…`
        : status.phase === "answer" ? `${nameOf(seats, status.answerer)} is answering…`
          : status.phase === "last_chance" ? "The spy is naming the place…"
            : turn ? "Pick a portrait above to vote." : "Everyone is voting…";
    return (
      <div className={`${styles.dock} ${turn ? styles.yourTurn : ""}`}>
        {turn && <p className={styles.turnNote}>{turn.prompt}</p>}
        <div className={styles.dockRow}>
          <span className={styles.muted} aria-live="polite">{waitingOn}</span>
          {status.waiting_for_next && <Button variant="surface" onClick={onNext}>Next ▸</Button>}
        </div>
      </div>
    );
  }

  const guessing = naming || turn.type === "last_chance";
  const value = guessing ? guess : text;
  const words = wordCount(value);
  const maxWords = guessing ? MAX_GUESS_WORDS : MAX_WORDS;
  const tooLong = words > maxWords || value.length > MAX_CHARS;
  const hedged = guessing && /,|\bor\b/i.test(value); // one place, not a list of options
  const needsTarget = turn.type === "ask" && !guessing && !target;
  const canSend = !busy && value.trim().length > 0 && !tooLong && !needsTarget && !hedged;

  const send = async (confirm = false) => {
    if (!canSend) return;
    const move: SpyMove = guessing
      ? { type: "guess", text: guess }
      : turn.type === "ask"
        ? { type: "ask", target: target!, text, confirm }
        : { type: "answer", text, confirm };
    setBusy(true);
    setError("");
    const r = await onMove(move);
    setBusy(false);
    if (r.ok) {
      setWarning(null);
      if (guessing) onGuess("");
      else setText("");
    } else if (r.warning) setWarning(r.warning);
    else setError(r.error ?? "That didn't go through.");
  };

  const placeholder = guessing
    ? "Name the place, e.g. a bowling alley"
    : turn.type === "ask"
      ? target ? `Ask ${nameOf(seats, target)} one question about the place…` : "Pick who to ask first"
      : "Your answer…";

  return (
    <form className={`${styles.dock} ${styles.yourTurn}`} onSubmit={(e) => { e.preventDefault(); send(); }}>
      <p className={styles.turnNote}>{guessing && turn.type === "ask" ? "Name the place. A wrong guess loses the game." : turn.prompt}</p>
      {turn.type === "ask" && turn.can_guess && (
        <div className={styles.modes} role="group" aria-label="Ask or name the place">
          <button type="button" aria-pressed={!naming} className={styles.mode} onClick={() => setNaming(false)}>Ask a question</button>
          <button type="button" aria-pressed={naming} className={styles.mode} onClick={() => setNaming(true)}>Name the place</button>
        </div>
      )}
      {turn.type === "ask" && !guessing && (
        <div className={styles.targets} role="group" aria-label="Who do you ask?">
          {turn.targets.map((pid) => {
            const s = seats.find((x) => x.id === pid);
            return (
              <button key={pid} type="button" className={styles.target} aria-pressed={target === pid}
                      onClick={() => { setTarget(pid); input.current?.focus(); }}>
                {s?.character && <Portrait character={s.character} size={32} />}
                {s?.name}
              </button>
            );
          })}
        </div>
      )}
      <div className={styles.dockRow}>
        <label htmlFor="spy-input" className="visually-hidden">{guessing ? "The place" : turn.type === "ask" ? "Your question" : "Your answer"}</label>
        <input id="spy-input" ref={input} className={styles.input} value={value} autoComplete="off"
               placeholder={placeholder} disabled={busy} maxLength={MAX_CHARS + 50}
               onChange={(e) => { (guessing ? onGuess : setText)(e.target.value); setWarning(null); }}
               onKeyDown={(e) => e.key === "Escape" && (guessing ? onGuess("") : setText(""))} />
        <Button variant="lantern" type="submit" disabled={!canSend}>
          {busy ? "Sending…" : guessing ? "Name it" : turn.type === "ask" ? "Ask" : "Answer"}
        </Button>
      </div>
      <div className={styles.dockMeta}>
        <span className={`meta ${tooLong ? styles.over : ""}`} aria-live="polite">{words} / {maxWords} words</span>
        {hedged && <span className={styles.error}>Name one place, without "or" or commas.</span>}
        {error && <span className={styles.error} role="alert">{error}</span>}
      </div>
      {warning && (
        <div className={styles.warning} role="alert">
          <span>{warning}</span>
          <div className={styles.warnActions}>
            <Button variant="coral" size="small" onClick={() => send(true)}>Send anyway</Button>
            <Button variant="ghost" size="small" onClick={() => { setWarning(null); input.current?.focus(); }}>Edit it</Button>
          </div>
        </div>
      )}
    </form>
  );
}
