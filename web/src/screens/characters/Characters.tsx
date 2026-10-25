import { CHARACTER_IDS } from "../../cast";
import { Portrait } from "../../components/Portrait";
import { SiteHeader } from "../../components/SiteHeader";
import { TraitBar } from "../../components/TraitBar";
import { useCast } from "../../useCast";
import styles from "./Characters.module.css";

/** The recurring cast: who they are, how they play. */
export function Characters() {
  const cast = useCast();
  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <SiteHeader current="characters" />
        <div>
          <span className={`meta ${styles.eyebrow}`}>The regulars</span>
          <h1 className={styles.title}>Meet the table.</h1>
          <p className={styles.lede}>
            The same eight characters play every game. Their voice shapes how they talk, whom they suspect and
            how they lie. You can turn their knobs in the lobby under Advanced settings.
          </p>
        </div>
        <div className={styles.grid}>
          {CHARACTER_IDS.map((id) => {
            const c = cast[id];
            return (
              <article key={id} className={styles.card}>
                <div className={styles.top}>
                  <Portrait character={id} mood="smug" size={96} shape="rounded" className={styles.portrait} />
                  <div className={styles.names}>
                    <span className={styles.name}>{c?.full_name ?? id}</span>
                    <span className={styles.voice} style={{ color: `var(--c-${id})` }}>{c?.voice}</span>
                  </div>
                </div>
                {c && <p className={styles.quote}>“{c.quote}”</p>}
                {c && (
                  <div>
                    <TraitBar label="Talkative" value={c.traits.talkative} />
                    <TraitBar label="Suspicious" value={c.traits.suspicious} />
                    <TraitBar label="Good liar" value={c.traits.liar} />
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
