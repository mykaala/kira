import { CHARACTER_IDS } from "../../cast";
import { Portrait, type Mood } from "../../components/Portrait";
import { useCast } from "../../useCast";
import styles from "./PortraitGallery.module.css";

const MOODS: Mood[] = ["neutral", "angry", "smug", "speaking", "dead"];

/** Every character in every mood, for checking the art against design/screens. Route: #/dev/portraits */
export function PortraitGallery() {
  const cast = useCast();
  return (
    <div className="lantern-page">
      <main className={styles.page}>
        <h1 className={styles.title}>Portraits</h1>
        <p className={styles.lede}>Every cast member in every mood. Moods change only brows, eyes and mouth.</p>
        <div className={styles.grid} role="table" aria-label="Portraits by character and mood">
          <span />
          {MOODS.map((m) => (
            <span key={m} className={`meta ${styles.head} ${styles.cell}`} role="columnheader">{m}</span>
          ))}
          {CHARACTER_IDS.map((id) => (
            <div key={id} style={{ display: "contents" }} role="row">
              <div className={styles.who} role="rowheader">
                <span className={styles.name}>{cast[id]?.full_name ?? id}</span>
                <span className={styles.voice}>{cast[id]?.voice}</span>
              </div>
              {MOODS.map((m) => (
                <div key={m} className={styles.cell} role="cell">
                  <Portrait character={id} mood={m} size={88} label={`${cast[id]?.name ?? id}, ${m}`} />
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className={styles.hero}>
          {CHARACTER_IDS.slice(0, 4).map((id) => (
            <Portrait key={id} character={id} mood="speaking" size={220} shape="rounded" className={styles.heroPortrait} />
          ))}
        </div>
      </main>
    </div>
  );
}
