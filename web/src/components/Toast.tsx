import { Button } from "./Button";
import styles from "./Toast.module.css";

export type ToastItem = { id: number; text: string; retry?: () => void };

/** Errors that don't stop the page: each with a retry when there is something to retry. */
export function Toasts({ items, onDismiss }: { items: ToastItem[]; onDismiss: (id: number) => void }) {
  if (!items.length) return null;
  return (
    <div className={styles.stack} role="region" aria-label="Messages">
      {items.map((t) => (
        <div key={t.id} className={styles.toast} role="alert">
          <span className={styles.text}>{t.text}</span>
          {t.retry && (
            <Button variant="lantern" size="small" onClick={() => { onDismiss(t.id); t.retry!(); }}>Retry</Button>
          )}
          <button type="button" className={styles.close} aria-label="Dismiss" onClick={() => onDismiss(t.id)}>✕</button>
        </div>
      ))}
    </div>
  );
}
