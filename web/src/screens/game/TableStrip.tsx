import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Portrait } from "../../components/Portrait";
import { CUES, cueColor, type Mark, type Marks } from "../../game/marks";
import { ROLE_COLOR, type Seat } from "../../game/model";
import styles from "./TableStrip.module.css";

/** Every living player as a compact chip; the speaker's chip is lit, and whoever they name reacts in a
 * thought bubble. Click a chip to note your read. */
export function TableStrip({ seats, speaking, typing, leanings, reactions, reactKey, acted, phase, marks, onMark, guesses }: {
  seats: Seat[];
  guesses: string[]; // roles you can guess
  speaking: string | null;
  typing: boolean;
  reactions: Record<string, string>; // pid -> a small physical reaction to the latest line
  reactKey: number | null; // the line they react to, so each new line replays the bubble
  leanings: Record<string, string>;
  acted: Set<string>;
  phase: string;
  marks: Marks;
  onMark: (pid: string, m: Mark) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const strip = useRef<HTMLElement>(null);
  useEffect(() => {
    // on narrow screens the strip scrolls sideways: bring the speaker's chip into view
    const el = strip.current;
    const chip = el?.querySelector<HTMLElement>(`[data-seat="${speaking}"]`);
    if (el && chip && el.scrollWidth > el.clientWidth) {
      el.scrollTo({ left: chip.offsetLeft - (el.clientWidth - chip.offsetWidth) / 2, behavior: "smooth" });
    }
  }, [speaking]);
  const name = (pid: string) => seats.find((s) => s.id === pid)?.name ?? "?";
  const living = seats.filter((s) => s.alive);
  const gone = seats.filter((s) => !s.alive);

  const statusLine = (s: Seat) => {
    if (s.you) return <span className={styles.status} style={{ color: ROLE_COLOR[s.role ?? ""] }}>{s.role}</span>;
    if (s.id === speaking) {
      return (
        <span className={styles.status}>
          {typing ? <span className={styles.talking} aria-label="talking"><i /><i /><i /></span> : "speaking"}
        </span>
      );
    }
    if ((phase === "vote" || phase === "night") && acted.has(s.id))
      return <span className={styles.status}>{phase === "vote" ? "voted" : "done"}</span>;
    if (leanings[s.id]) return <span className={`${styles.status} ${styles.lean}`}>→ {name(leanings[s.id])}</span>;
    return <span className={styles.status}>{phase === "discussion" ? "undecided" : "waiting"}</span>;
  };

  return (
    <section aria-label="The table" className={styles.strip} ref={strip}>
      {living.map((s) => {
        const mark = marks[s.id] ?? {};
        const cls = [styles.seat, s.id === speaking && styles.speaking, s.id === speaking && typing && styles.pulse,
          s.you && styles.you].filter(Boolean).join(" ");
        return (
          <div key={s.id} className={styles.seatWrap} data-seat={s.id}>
            {reactions[s.id] && (
              <span key={`${reactKey}-${s.id}`} className={styles.thought} role="status">{reactions[s.id]}</span>
            )}
            <button
              type="button"
              className={cls}
              onClick={() => !s.you && setOpen(open === s.id ? null : s.id)}
              aria-label={s.you ? "You" : `${s.name}: your read`}
              aria-expanded={s.you ? undefined : open === s.id}
            >
              {s.character ? (
                <span
                  className={`${styles.face} ${mark.cue ? styles.ring : ""}`}
                  style={{ "--cue": cueColor(mark.cue) } as React.CSSProperties}
                >
                  <Portrait character={s.character} mood={s.id === speaking ? "speaking" : "neutral"} size={56} />
                  {acted.has(s.id) && (phase === "vote" || phase === "night") && <span className={styles.tick}>✓</span>}
                </span>
              ) : (
                <span className={styles.youFace}>You</span>
              )}
              <span className={styles.text}>
                <strong className={styles.name}>{s.you ? "You" : s.name}</strong>
                {statusLine(s)}
                {(mark.role || mark.note) && (
                  <span className={styles.guess}>{[mark.role && `${mark.role}?`, mark.note].filter(Boolean).join(" · ")}</span>
                )}
              </span>
            </button>
            {open === s.id && (
              <ReadPopover seat={s} mark={mark} guesses={guesses} onMark={(m) => onMark(s.id, m)}
                           onClose={() => setOpen(null)} />
            )}
          </div>
        );
      })}
      {gone.length > 0 && (
        <div className={styles.gone}>
          {gone.map((s) => (
            <span key={s.id} className={styles.ghost} title={`${s.you ? "You" : s.name}${s.role ? ` (${s.role})` : ""}`}>
              {s.you ? "Y" : s.name[0]}
            </span>
          ))}
          <span className={styles.goneLabel}>gone</span>
        </div>
      )}
    </section>
  );
}

/** Your read on one player: a cue, a role guess, a short note. Floats under their chip (flipped to the
 * left edge when it would run off screen), or sits in place in the notes. */
export function ReadPopover({ seat, mark, guesses, onMark, onClose, inline = false }: {
  seat: Seat;
  guesses: string[];
  mark: Mark;
  onMark: (m: Mark) => void;
  onClose: () => void;
  inline?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [flip, setFlip] = useState(false);
  useLayoutEffect(() => {
    const r = ref.current?.getBoundingClientRect();
    if (!inline && r && r.right > window.innerWidth - 16) setFlip(true);
  }, [inline]);
  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (ref.current && !ref.current.parentElement?.contains(e.target as Node)) onClose();
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [onClose]);

  return (
    <div ref={ref} className={`${styles.popover} ${flip ? styles.flip : ""} ${inline ? styles.inline : ""}`} role="dialog" aria-label={`Your read on ${seat.name}`}>
      <div className={styles.popTitle}>Your read on {seat.name}</div>
      <div className={styles.row}>
        {CUES.map((c) => (
          <button key={c.id} type="button" className={`${styles.opt} ${mark.cue === c.id ? styles.on : ""}`}
                  style={{ "--opt": c.color } as React.CSSProperties} aria-pressed={mark.cue === c.id}
                  onClick={() => onMark({ ...mark, cue: mark.cue === c.id ? undefined : c.id })}>
            {c.label}
          </button>
        ))}
      </div>
      <span className={`meta ${styles.sub}`}>Their role?</span>
      <div className={`${styles.row} ${styles.row3}`}>
        {guesses.map((r) => (
          <button key={r} type="button" className={`${styles.opt} ${mark.role === r ? styles.on : ""}`}
                  style={{ "--opt": ROLE_COLOR[r] } as React.CSSProperties} aria-pressed={mark.role === r}
                  onClick={() => onMark({ ...mark, role: mark.role === r ? undefined : r })}>
            {r}
          </button>
        ))}
      </div>
      <label className="visually-hidden" htmlFor={`note-${seat.id}`}>Note on {seat.name}</label>
      <input id={`note-${seat.id}`} className={styles.note} autoFocus maxLength={40} value={mark.note ?? ""}
             placeholder="e.g. claimed doctor" onChange={(e) => onMark({ ...mark, note: e.target.value })}
             onKeyDown={(e) => e.key === "Enter" && onClose()} />
    </div>
  );
}
