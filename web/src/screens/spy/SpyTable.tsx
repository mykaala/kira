import { useEffect, useRef, useState } from "react";
import { Portrait } from "../../components/Portrait";
import { cueColor, type Cue, type Mark, type Marks } from "../../game/marks";
import type { SpySeat } from "../../spy/seats";
import styles from "../game/TableStrip.module.css";
import own from "./SpyGame.module.css";

/** Your reads, worded for this game ("mafia" is the strongest cue's stored id). */
const SPY_CUES: { id: Cue; label: string; color: string }[] = [
  { id: "trust", label: "Trust", color: "var(--teal)" },
  { id: "unsure", label: "Unsure", color: "var(--muted)" },
  { id: "suspect", label: "Suspect", color: "var(--lantern)" },
  { id: "mafia", label: "Spy!", color: "var(--coral)" },
];

/** Everyone at the table: name, how many questions they've asked and answered, the speaker lit up, and
 * your own read on them (click a chip). No voice labels during play. */
export function SpyTable({ seats, speaking, asked, answered, marks, onMark }: {
  seats: SpySeat[];
  speaking: string | null;
  asked: Record<string, number>;
  answered: Record<string, number>;
  marks: Marks;
  onMark: (pid: string, m: Mark) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const strip = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = strip.current;
    const chip = el?.querySelector<HTMLElement>(`[data-seat="${speaking}"]`);
    if (el && chip && el.scrollWidth > el.clientWidth) {
      el.scrollTo({ left: chip.offsetLeft - (el.clientWidth - chip.offsetWidth) / 2, behavior: "smooth" });
    }
  }, [speaking]);

  return (
    <section aria-label="The table" className={styles.strip} ref={strip}>
      {seats.map((s) => {
        const mark = marks[s.id] ?? {};
        const read = SPY_CUES.find((c) => c.id === mark.cue)?.label;
        const cls = [styles.seat, s.id === speaking && styles.speaking, s.you && styles.you, !s.alive && own.outSeat]
          .filter(Boolean).join(" ");
        return (
          <div key={s.id} className={styles.seatWrap} data-seat={s.id}>
            <button type="button" className={cls} onClick={() => !s.you && setOpen(open === s.id ? null : s.id)}
                    aria-label={s.you ? (s.alive ? "You" : "You: voted out, a civilian")
                      : `${s.name}${s.alive ? "" : ": voted out, a civilian"}: asked ${asked[s.id] ?? 0}, answered ${answered[s.id] ?? 0}. Your read${read ? `: ${read}` : ""}`}
                    aria-expanded={s.you ? undefined : open === s.id}>
              {s.character ? (
                <span className={`${styles.face} ${mark.cue ? styles.ring : ""}`}
                      style={{ "--cue": cueColor(mark.cue) } as React.CSSProperties}>
                  <Portrait character={s.character} mood={s.id === speaking ? "speaking" : "neutral"} size={56} />
                </span>
              ) : (
                <span className={styles.youFace}>You</span>
              )}
              <span className={styles.text}>
                <strong className={styles.name}>{s.you ? "You" : s.name}</strong>
                <span className={styles.status}>
                  {!s.alive ? <span className={own.outTag}>out · civilian</span>
                    : <>{s.id === speaking ? "speaking · " : ""}Q {asked[s.id] ?? 0} · A {answered[s.id] ?? 0}</>}
                </span>
                {(read || mark.note) && (
                  <span className={styles.guess}>{[read, mark.note].filter(Boolean).join(" · ")}</span>
                )}
              </span>
            </button>
            {open === s.id && <ReadPopover seat={s} mark={mark} onMark={(m) => onMark(s.id, m)} onClose={() => setOpen(null)} />}
          </div>
        );
      })}
    </section>
  );
}

function ReadPopover({ seat, mark, onMark, onClose }: {
  seat: SpySeat;
  mark: Mark;
  onMark: (m: Mark) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
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
    <div ref={ref} className={styles.popover} role="dialog" aria-label={`Your read on ${seat.name}`}>
      <div className={styles.popTitle}>Your read on {seat.name}</div>
      <div className={styles.row}>
        {SPY_CUES.map((c) => (
          <button key={c.id} type="button" className={`${styles.opt} ${mark.cue === c.id ? styles.on : ""}`}
                  style={{ "--opt": c.color } as React.CSSProperties} aria-pressed={mark.cue === c.id}
                  onClick={() => onMark({ ...mark, cue: mark.cue === c.id ? undefined : c.id })}>
            {c.label}
          </button>
        ))}
      </div>
      <label className="visually-hidden" htmlFor={`note-${seat.id}`}>Note on {seat.name}</label>
      <input id={`note-${seat.id}`} className={styles.note} autoFocus maxLength={40} value={mark.note ?? ""}
             placeholder="e.g. vague about the smell" onChange={(e) => onMark({ ...mark, note: e.target.value })}
             onKeyDown={(e) => e.key === "Enter" && onClose()} />
    </div>
  );
}
