import { CandleTimer } from "../../components/CandleTimer";
import type { Status } from "../../types";
import styles from "./PhaseBar.module.css";

const PHASE_LABEL: Record<string, string> = {
  night: "Night",
  morning: "Morning",
  discussion: "Debate",
  vote: "Vote",
};

function candle(status: Status) {
  if (status.phase === "discussion" && status.turns_total > 0) {
    const left = status.turns_left;
    return {
      value: left / status.turns_total,
      label: `${left} ${left === 1 ? "turn" : "turns"} left`,
      aria: `${left} ${left === 1 ? "turn" : "turns"} left before the vote`,
    };
  }
  if (status.phase === "vote") return { value: 0, label: "voting", aria: "The vote is open" };
  return { value: 1, label: status.phase === "night" ? "night" : "dawn", aria: `It is ${status.phase}` };
}

export function PhaseBar({ status }: { status: Status }) {
  const c = candle(status);
  return (
    <header className={styles.bar}>
      <div className={styles.day}>
        <span className={styles.dayLabel}>Day {status.day}</span>
        <span className={`meta ${styles.phase}`}>Mafia · {PHASE_LABEL[status.phase] ?? status.phase}</span>
      </div>
      <CandleTimer value={c.value} label={c.label} ariaLabel={c.aria} />
    </header>
  );
}
