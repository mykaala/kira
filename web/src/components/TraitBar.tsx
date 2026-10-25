import styles from "./TraitBar.module.css";

/** A 0..1 trait as a bar, or as a slider when `onChange` is given. */
export function TraitBar({ label, value, onChange }: { label: string; value: number; onChange?: (v: number) => void }) {
  const pct = `${Math.round(value * 100)}%`;
  const Row = onChange ? "label" : "div";
  return (
    <Row className={styles.row}>
      <span className={styles.label}>{label}</span>
      {onChange ? (
        <input type="range" min={0} max={1} step={0.05} value={value} className={styles.range}
               style={{ "--pct": pct } as React.CSSProperties} onChange={(e) => onChange(Number(e.target.value))} />
      ) : (
        <span className={styles.bar} role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={value} aria-label={label}>
          <span className={styles.fill} style={{ width: pct }} />
        </span>
      )}
      <span className={styles.value}>{pct}</span>
    </Row>
  );
}
