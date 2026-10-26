import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { nameOf, type SpySeat } from "../../spy/seats";
import { MAX_CHARS, MAX_GUESS_WORDS, MAX_WORDS, wordCount, type SpyMove, type SpyStatus } from "../../spy/types";
import styles from "./SpyGame.module.css";

export type MoveResult = { ok: true } | { ok: false; warning?: string; error?: string };

/** The one input area: it adapts to your turn (ask, answer, name the place) with a clear prompt, a word
 * counter and Enter to send. Votes are cast on the stage. Off-turn it shows who you're waiting on, and the spy
 * may name the place from there while questions are under way. */
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
  const [naming, setNaming] = useState(false); // the spy chose to name the place instead of asking or answering
  const [busy, setBusy] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [sentFor, setSentFor] = useState<string | null>(null); // the turn the server took your move for
  const sending = useRef(false); // set synchronously, so a fast double submit sends one request
  const input = useRef<HTMLInputElement>(null);
  const key = turn ? `${status.round}:${turn.type}:${status.questions}` : `none:${status.round}:${status.phase}:${status.questions}`;
  const offTurn = !turn && status.can_guess; // the spy, while someone else is asking or answering
  const sent = sentFor === key; // status.turn lags until the reveals finish

  useEffect(() => {
    setText("");
    setTarget(turn?.targets.length === 1 ? turn.targets[0] : null);
    // a guess you're writing carries over into your own turn to ask or answer; a vote ends it
    setNaming((n) => turn?.type === "last_chance" || (n && turn?.type !== "vote" && turn?.type !== "revote"));
    setWarning(null);
    setError("");
    if (turn && turn.type !== "vote" && turn.type !== "revote") requestAnimationFrame(() => input.current?.focus());
  }, [key]); // reset only when a new turn starts

  if ((!turn || turn.type === "vote" || turn.type === "revote" || sent) && !(offTurn && naming && !sent)) {
    const waitingOn = sent ? "Sent. Waiting for the others…"
      : status.phase === "ask" ? `${nameOf(seats, status.asker)} is asking…`
        : status.phase === "answer" ? `${nameOf(seats, status.answerer)} is answering…`
          : status.phase === "last_chance" ? "The spy is naming the place…"
            : turn ? "Pick a portrait above to vote." : "Everyone is voting…";
    return (
      <div className={`${styles.dock} ${turn && !sent ? styles.yourTurn : ""}`}>
        {turn && !sent && <p className={styles.turnNote}>{turn.prompt}</p>}
        <div className={styles.dockRow}>
          <span className={styles.muted} aria-live="polite">{waitingOn}</span>
          {offTurn && !sent && (
            <Button variant="surface" onClick={() => { setNaming(true); requestAnimationFrame(() => input.current?.focus()); }}>
              Name the place
            </Button>
          )}
          {status.waiting_for_next && <Button variant="surface" onClick={onNext}>Next ▸</Button>}
        </div>
      </div>
    );
  }

  const type = turn?.type ?? "guess"; // no turn: the spy naming the place out of turn
  const guessing = naming || type === "last_chance";
  const value = guessing ? guess : text;
  const words = wordCount(value);
  const maxWords = guessing ? MAX_GUESS_WORDS : MAX_WORDS;
  const tooLong = words > maxWords || value.length > MAX_CHARS;
  const hedged = guessing && /,|\bor\b/i.test(value); // one place, not a list of options
  const needsTarget = type === "ask" && !guessing && !target;
  const canSend = !busy && value.trim().length > 0 && !tooLong && !needsTarget && !hedged;

  const send = async (confirm = false) => {
    if (!canSend || sending.current) return;
    const move: SpyMove = guessing
      ? { type: "guess", text: guess }
      : type === "ask"
        ? { type: "ask", target: target!, text, confirm }
        : { type: "answer", text, confirm };
    sending.current = true;
    setBusy(true);
    setError("");
    const r = await onMove(move);
    sending.current = false;
    setBusy(false);
    if (r.ok) {
      setSentFor(key);
      setWarning(null);
      if (guessing) onGuess("");
      else setText("");
    } else if (r.warning) setWarning(r.warning);
    else setError(r.error ?? "That didn't go through.");
  };

  const placeholder = guessing
    ? "Name the place, e.g. a bowling alley"
    : type === "ask"
      ? target ? `Ask ${nameOf(seats, target)} one question about the place…` : "Pick who to ask first"
      : "Your answer…";

  return (
    <form className={`${styles.dock} ${styles.yourTurn}`} onSubmit={(e) => { e.preventDefault(); send(); }}>
      <p className={styles.turnNote}>
        {!turn ? "Name the place now, before the next line. A wrong guess loses the game."
          : guessing && type !== "last_chance" ? "Name the place. A wrong guess loses the game." : turn.prompt}
      </p>
      {(turn?.can_guess || !turn) && (
        <div className={styles.modes} role="group" aria-label={`${type === "answer" ? "Answer" : type === "ask" ? "Ask" : "Wait"} or name the place`}>
          <button type="button" aria-pressed={!naming} className={styles.mode} onClick={() => setNaming(false)}>
            {type === "ask" ? "Ask a question" : type === "answer" ? "Answer" : "Keep listening"}
          </button>
          <button type="button" aria-pressed={naming} className={styles.mode} onClick={() => setNaming(true)}>Name the place</button>
        </div>
      )}
      {turn?.type === "ask" && !guessing && (
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
        <label htmlFor="spy-input" className="visually-hidden">{guessing ? "The place" : type === "ask" ? "Your question" : "Your answer"}</label>
        <input id="spy-input" ref={input} className={styles.input} value={value} autoComplete="off"
               placeholder={placeholder} disabled={busy} maxLength={MAX_CHARS + 50}
               onChange={(e) => { (guessing ? onGuess : setText)(e.target.value); setWarning(null); }}
               onKeyDown={(e) => e.key === "Escape" && (guessing ? onGuess("") : setText(""))} />
        <Button variant="lantern" type="submit" disabled={!canSend}>
          {busy ? "Sending…" : guessing ? "Name it" : type === "ask" ? "Ask" : "Answer"}
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
