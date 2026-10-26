/** The pieces every game's lobby is built from, so they all look and behave alike: the one-screen frame, the
 * table you swap seats at, and switch pills for a game's extras. */
import { useEffect, useState, type ReactNode } from "react";
import { benchOf, drawCast, type CharacterId } from "../../cast";
import { Button } from "../../components/Button";
import { RedrawIcon } from "../../components/Icons";
import { LanternMark } from "../../components/LanternMark";
import { Portrait } from "../../components/Portrait";
import { useCast } from "../../useCast";
import { RoundTable } from "./RoundTable";
import styles from "./Lobby.module.css";

/** Back link and crumbs on top; the table on the left; house rules and the start button centred on the right.
 * From 900×640 up it all fits one screen. */
export function LobbyFrame({ game, title, sub, table, onSubmit, children }: {
  game: string;
  title: string;
  sub: string;
  table: ReactNode;
  onSubmit: (e: React.FormEvent) => void;
  children: ReactNode;
}) {
  return (
    <div className="lantern-page">
      <form className={`${styles.page} ${styles.fit}`} onSubmit={onSubmit}>
        <header className={styles.header}>
          <div className={styles.crumbs}>
            <a href="#/" className={styles.back} aria-label="Back to games">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true">
                <path d="M19 12H5M11 6l-6 6 6 6" />
              </svg>
            </a>
            <span className={styles.word}>Kira</span>
            <span className={`meta ${styles.path}`}>/ {game} / Set the table</span>
          </div>
        </header>
        <div className={styles.columns}>
          <section className={styles.left}>
            <div className={styles.heading}>
              <h1 className={styles.title}>{title}</h1>
              <p className={styles.sub}>{sub}</p>
            </div>
            {table}
          </section>
          <div className={styles.right}>{children}</div>
        </div>
      </form>
    </div>
  );
}

/** The table, every seat a real character. Its middle shows who's hiding and Redraw; tap a seat and it shows who's
 * waiting to swap in. */
export function SeatTable({ seats, onSeats, minSeats, hiding, count }: {
  seats: CharacterId[];
  onSeats: (next: CharacterId[]) => void;
  minSeats: number;
  hiding: string; // "Mafia hiding", "spy hiding"
  count: number; // how many are hiding
}) {
  const cast = useCast();
  const [selected, setSelected] = useState<CharacterId | null>(null);
  const sel = selected && seats.includes(selected) ? selected : null;
  const bench = benchOf(seats);
  const nameOf = (id: CharacterId) => cast[id]?.name ?? id;

  useEffect(() => {
    if (!sel) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSelected(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sel]);

  const swapIn = (id: CharacterId) => {
    if (sel) onSeats(seats.map((c) => (c === sel ? id : c)));
    setSelected(null);
  };
  const empty = (id: CharacterId) => {
    onSeats(seats.filter((c) => c !== id));
    setSelected(null);
  };

  const center = sel ? (
    <div className={styles.swap}>
      <span className={styles.swapTitle}>Swap <strong>{nameOf(sel)}</strong> for…</span>
      {bench.length > 0 ? (
        <div className={styles.swapFaces}>
          {bench.map((id) => (
            <button key={id} type="button" className={styles.swapFace} title={nameOf(id)}
                    aria-label={`Swap ${nameOf(sel)} for ${nameOf(id)}`} onClick={() => swapIn(id)}>
              <Portrait character={id} size={56} />
            </button>
          ))}
        </div>
      ) : (
        <span className={styles.hint}>Everyone is already seated.</span>
      )}
      <div className={styles.swapActions}>
        <Button variant="ghost" size="small" disabled={seats.length <= minSeats} onClick={() => empty(sel)}>Empty seat</Button>
        <Button variant="ghost" size="small" onClick={() => setSelected(null)}>Keep</Button>
      </div>
    </div>
  ) : (
    <>
      <LanternMark size={40} />
      <span className={styles.count}>{count} among {seats.length + 1}</span>
      <span className={`meta ${styles.hiding}`}>{hiding}</span>
      <button type="button" className={styles.redraw} disabled={bench.length === 0}
              onClick={() => onSeats(drawCast(seats.length, seats))}>
        <RedrawIcon size={16} /> Redraw
      </button>
    </>
  );

  return <RoundTable seats={seats} mafia={count} cast={cast} selected={sel} onSelect={setSelected} center={center} />;
}

/** One more random character at the table, or the last one up. */
export const addSeat = (seats: CharacterId[]) => {
  const bench = benchOf(seats);
  return [...seats, bench[Math.floor(Math.random() * bench.length)]];
};
export const dropSeat = (seats: CharacterId[]) => seats.slice(0, -1);

export type Pill = { id: string; name: string; tone: string; on: boolean; fixed?: boolean; hint?: string };

/** A game's roles or extras as a 2×2 grid of pills: fixed ones show ✓, the rest are switches. One line under them
 * says what the switched-on ones do, or `idle` when none are on. */
export function SwitchPills({ label, pills, idle, onToggle }: {
  label: string;
  pills: Pill[];
  idle: string;
  onToggle: (id: string) => void;
}) {
  const on = pills.filter((p) => !p.fixed && p.on && p.hint);
  return (
    <div className={styles.field}>
      <span className={`meta ${styles.label}`}>{label}</span>
      <ul className={styles.roles}>
        {pills.map((p) => {
          const tone = { "--tone": p.tone } as React.CSSProperties;
          return (
            <li key={p.id}>
              {p.fixed ? (
                <div className={`${styles.role} ${styles.fixed}`} style={tone}>
                  <span className={styles.roleName}>{p.name}</span>
                  <span className={styles.always} aria-label="always in">✓</span>
                </div>
              ) : (
                <button type="button" className={styles.role} style={tone} aria-pressed={p.on} title={p.hint}
                        onClick={() => onToggle(p.id)}>
                  <span className={styles.roleName}>{p.name}</span>
                  <span className={styles.switch} aria-hidden="true" />
                </button>
              )}
            </li>
          );
        })}
      </ul>
      <p className={styles.hint}>{on.length ? on.map((p) => p.hint).join(" ") : idle}</p>
    </div>
  );
}

/** A − n + stepper. */
export function Stepper({ label, value, min, max, onChange }: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (next: number) => void;
}) {
  const id = `stepper-${label.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <div className={styles.field}>
      <span className={`meta ${styles.label}`} id={id}>{label}</span>
      <div className={styles.stepper} role="group" aria-labelledby={id}>
        <button type="button" className={styles.step} aria-label="One fewer" disabled={value <= min}
                onClick={() => onChange(value - 1)}>−</button>
        <span className={styles.stepValue} aria-live="polite">{value}</span>
        <button type="button" className={styles.step} aria-label="One more, at random" disabled={value >= max}
                onClick={() => onChange(value + 1)}>+</button>
      </div>
    </div>
  );
}
