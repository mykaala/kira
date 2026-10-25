import { Button } from "../../components/Button";
import { CandleTimer } from "../../components/CandleTimer";
import type { Speed } from "../../useGame";
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

export function PhaseBar({ status, canCallVote, onCallVote, auto, onAuto, speed, onSpeed }: {
  status: Status;
  canCallVote: boolean;
  onCallVote: () => void;
  auto: boolean;
  onAuto: (on: boolean) => void;
  speed: Speed;
  onSpeed: (s: Speed) => void;
}) {
  const c = candle(status);
  return (
    <header className={styles.bar}>
      <div className={styles.day}>
        <span className={styles.dayLabel}>Day {status.day}</span>
        <span className={`meta ${styles.phase}`}>Mafia · {PHASE_LABEL[status.phase] ?? status.phase}</span>
      </div>
      <CandleTimer value={c.value} label={c.label} ariaLabel={c.aria} />
      <div className={styles.pace}>
        <label className={styles.toggle} title="Let the AI players talk without waiting for you">
          <input type="checkbox" checked={auto} onChange={(e) => onAuto(e.target.checked)} />
          Auto
        </label>
        <label className={styles.toggle} title="How fast messages type out and results are revealed">
          Pace
          <select value={speed} onChange={(e) => onSpeed(e.target.value as Speed)}>
            <option value="slow">Slow</option>
            <option value="normal">Normal</option>
            <option value="fast">Fast</option>
          </select>
        </label>
      </div>
      <Button variant="coral" onClick={onCallVote} disabled={!canCallVote}>Call the vote</Button>
    </header>
  );
}
