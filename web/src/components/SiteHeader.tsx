import { LanternMark } from "./LanternMark";
import styles from "./SiteHeader.module.css";

/** Logo and the top-level navigation. */
export function SiteHeader({ current }: { current: "play" | "characters" }) {
  return (
    <header className={styles.header}>
      <a href="#/" className={styles.brand} aria-label="Kira, home">
        <LanternMark />
        <span className={styles.word}>Kira</span>
      </a>
      <nav className={styles.nav} aria-label="Main">
        <a href="#/" className={`${styles.link} ${current === "play" ? styles.active : ""}`}
           aria-current={current === "play" ? "page" : undefined}>Play</a>
        <a href="#/characters" className={`${styles.link} ${current === "characters" ? styles.active : ""}`}
           aria-current={current === "characters" ? "page" : undefined}>Characters</a>
      </nav>
    </header>
  );
}
