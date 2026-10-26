import type { ReactNode } from "react";
import { LanternMark } from "../../components/LanternMark";
import { Portrait } from "../../components/Portrait";
import type { Character, CharacterId } from "../../cast";
import styles from "./RoundTable.module.css";

const RADIUS = 42; // % from the centre

/** Seats around a table, "You" at the bottom. Tapping a seat selects it. */
export function RoundTable({ seats, mafia, cast, selected, onSelect, hiding = "Mafia hiding", center }: {
  seats: CharacterId[];
  mafia: number;
  hiding?: string; // what is hiding at the table (another game: "a spy hiding")
  cast: Partial<Record<CharacterId, Character>>;
  selected: CharacterId | null;
  onSelect: (id: CharacterId | null) => void;
  center?: ReactNode; // replaces the "2 among 7" count in the middle of the table
}) {
  const total = seats.length + 1;
  const at = (i: number) => {
    const angle = Math.PI / 2 + ((i + 1) * 2 * Math.PI) / total; // seat 0 sits just clockwise of you
    return { left: `${50 + RADIUS * Math.cos(angle)}%`, top: `${50 + RADIUS * Math.sin(angle)}%` };
  };
  return (
    <div className={styles.table}>
      <div className={styles.top}>
        {center ?? (
          <>
            <LanternMark size={44} />
            <span className={styles.count}>{mafia} among {total}</span>
            <span className={`meta ${styles.hiding}`}>{hiding}</span>
          </>
        )}
      </div>
      {seats.map((id, i) => (
        <button key={id} type="button" style={at(i)} onClick={() => onSelect(id === selected ? null : id)}
                className={`${styles.seat} ${id === selected ? styles.selected : ""}`}
                aria-pressed={id === selected}
                aria-label={`Seat: ${cast[id]?.name ?? id}${cast[id] ? `, ${cast[id]!.voice.toLowerCase()}` : ""}`}>
          <Portrait character={id} size={92} className={styles.face} />
          <span className={styles.name}>{cast[id]?.name ?? id}</span>
        </button>
      ))}
      <div className={styles.seat} style={{ left: "50%", top: `${50 + RADIUS}%` }}>
        <span className={styles.you}>You</span>
        <span className={styles.yourSeat}>Your seat</span>
      </div>
    </div>
  );
}
