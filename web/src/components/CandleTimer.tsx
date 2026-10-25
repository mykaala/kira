import styles from "./CandleTimer.module.css";

/** A cream wax bar that burns down, with a flickering flame at its edge. `value` is 0..1 left. */
export function CandleTimer({ value, label, ariaLabel }: { value: number; label: string; ariaLabel: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={`${styles.timer} ${pct === 0 ? styles.out : ""}`} role="timer" aria-label={ariaLabel}>
      <div className={styles.track}>
        <div className={styles.wax} style={{ width: `${pct}%` }} />
        {pct > 0 && (
          <svg className={styles.flame} style={{ left: `calc(${pct}% - 11px)` }} width="22" height="30"
               viewBox="0 0 22 30" aria-hidden="true">
            <path d="M11 2 C18 11 18 18 11 26 C4 18 4 11 11 2 Z" fill="var(--lantern)" />
            <path d="M11 12 C14 16 14 19 11 23 C8 19 8 16 11 12 Z" fill="var(--coral)" />
          </svg>
        )}
      </div>
      <span className={styles.label}>{label}</span>
    </div>
  );
}
