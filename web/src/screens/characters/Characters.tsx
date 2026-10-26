import { CHARACTER_IDS, type CharacterId, type Traits } from "../../cast";
import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { SiteHeader } from "../../components/SiteHeader";
import { TraitBar } from "../../components/TraitBar";
import { DIFFICULTIES, effectiveTraits, useShifts, type Tuning } from "../../game/tuning";
import { useCast } from "../../useCast";
import styles from "./Characters.module.css";

/** The recurring cast: who they are, and how sharp they play. A difficulty sets everyone at once; a knob turned
 * by hand wins over it for that character until it's reset. */
export function Characters({ tuning, onChange }: { tuning: Tuning; onChange: (t: Tuning) => void }) {
  const cast = useCast();
  const shifts = useShifts();
  const level = DIFFICULTIES.find((d) => d.id === tuning.difficulty) ?? DIFFICULTIES[1];
  const handSet = Object.keys(tuning.traits).length;

  const traitsOf = (id: CharacterId, base: Traits) => effectiveTraits(base, tuning, id, shifts);
  const turn = (id: CharacterId, base: Traits, key: keyof Traits, v: number) =>
    onChange({ ...tuning, traits: { ...tuning.traits, [id]: { ...traitsOf(id, base), [key]: v } } });
  const reset = (id: CharacterId) => {
    const { [id]: _, ...rest } = tuning.traits;
    onChange({ ...tuning, traits: rest });
  };

  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <SiteHeader current="characters" />
        <div>
          <span className={`meta ${styles.eyebrow}`}>The regulars</span>
          <h1 className={styles.title}>Meet the table.</h1>
          <p className={styles.lede}>
            The same eight characters play every game. Their voice shapes how they talk, whom they suspect and how they
            lie. Set how sharp they play here.
          </p>
        </div>

        <section className={styles.sharp} aria-labelledby="sharp-title">
          <div className={styles.sharpHead}>
            <h2 className={styles.h2} id="sharp-title">How sharp are they?</h2>
            <span className={`meta ${styles.note}`}>Mafia only, for now</span>
          </div>
          <div className={styles.levels} role="radiogroup" aria-labelledby="sharp-title">
            {DIFFICULTIES.map((d) => (
              <button key={d.id} type="button" role="radio" aria-checked={d.id === tuning.difficulty}
                      className={`${styles.level} ${styles[d.id]}`} onClick={() => onChange({ ...tuning, difficulty: d.id })}>
                <span className={styles.levelName}>{d.label}</span>
                <span className={styles.levelBlurb}>{d.blurb}</span>
              </button>
            ))}
          </div>
          {handSet > 0 && (
            <div className={styles.handSet}>
              <span>
                {handSet === 1 ? "1 character is" : `${handSet} characters are`} set by hand.
              </span>
              <Button variant="ghost" size="small" onClick={() => onChange({ ...tuning, traits: {} })}>
                Reset all to {level.label}
              </Button>
            </div>
          )}
        </section>

        <div className={styles.grid}>
          {CHARACTER_IDS.map((id) => {
            const c = cast[id];
            const custom = !!tuning.traits[id];
            const t = c && traitsOf(id, c.traits);
            return (
              <article key={id} className={`${styles.card} ${custom ? styles.custom : ""}`}>
                <div className={styles.top}>
                  <Portrait character={id} mood="smug" size={96} shape="rounded" className={styles.portrait} />
                  <div className={styles.names}>
                    <span className={styles.name}>{c?.full_name ?? id}</span>
                    <span className={styles.voice} style={{ color: `var(--c-${id})` }}>{c?.voice}</span>
                  </div>
                </div>
                {c && <p className={styles.quote}>“{c.quote}”</p>}
                {c && t && (
                  <div className={styles.knobs}>
                    <TraitBar label="Talkative" value={t.talkative} onChange={(v) => turn(id, c.traits, "talkative", v)} />
                    <TraitBar label="Suspicious" value={t.suspicious} onChange={(v) => turn(id, c.traits, "suspicious", v)} />
                    <TraitBar label="Good liar" value={t.liar} onChange={(v) => turn(id, c.traits, "liar", v)} />
                  </div>
                )}
                <div className={styles.foot}>
                  <span className={`meta ${styles.tag}`}>{custom ? "Set by hand" : level.label}</span>
                  {custom && <Button variant="ghost" size="small" onClick={() => reset(id)}>Reset to {level.label}</Button>}
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
