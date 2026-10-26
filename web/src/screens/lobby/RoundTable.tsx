import { LanternMark } from "../../components/LanternMark";
import { Portrait } from "../../components/Portrait";
import type { Character, CharacterId } from "../../cast";
import styles from "./RoundTable.module.css";

const RADIUS = 42; // % from the centre

/** Seats around a table, "You" at the bottom. With no cast chosen, the AI seats are a mystery. */
export function RoundTable({ seats, mafia, cast, selected, onSelect, hiding = "Mafia hiding" }: {
  seats: (CharacterId | null)[]; // null = a random, unknown seat
  mafia: number;
  hiding?: string; // what is hiding at the table (another game: "a spy hiding")
  cast: Partial<Record<CharacterId, Character>>;
  selected: CharacterId | null;
  onSelect: (id: CharacterId | null) => void;
}) {
  const total = seats.length + 1;
  const at = (i: number) => {
    const angle = Math.PI / 2 + ((i + 1) * 2 * Math.PI) / total; // seat 0 sits just clockwise of you
    return { left: `${50 + RADIUS * Math.cos(angle)}%`, top: `${50 + RADIUS * Math.sin(angle)}%` };
  };
  return (
    <div className={styles.table}>
      <div className={styles.top}>
        <LanternMark size={44} />
        <span className={styles.count}>{mafia} among {total}</span>
        <span className={`meta ${styles.hiding}`}>{hiding}</span>
      </div>
      {seats.map((id, i) =>
        id ? (
          <button key={id} type="button" style={at(i)} onClick={() => onSelect(id === selected ? null : id)}
                  className={`${styles.seat} ${id === selected ? styles.selected : ""}`}
                  aria-pressed={id === selected}
                  aria-label={`Seat: ${cast[id]?.name ?? id}${cast[id] ? `, ${cast[id]!.voice.toLowerCase()}` : ""}`}>
            <Portrait character={id} size={92} className={styles.face} />
            <span className={styles.name}>{cast[id]?.name ?? id}</span>
          </button>
        ) : (
          <button key={`mystery-${i}`} type="button" style={at(i)} className={styles.seat} onClick={() => onSelect(null)}
                  aria-label="A random seat: dealt when the lantern goes dark">
            <span className={styles.mystery} aria-hidden="true">?</span>
            <span className={styles.name}>random</span>
          </button>
        ),
      )}
      <div className={styles.seat} style={{ left: "50%", top: `${50 + RADIUS}%` }}>
        <span className={styles.you}>You</span>
        <span className={styles.yourSeat}>Your seat</span>
      </div>
    </div>
  );
}
