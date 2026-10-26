import { Button } from "../../components/Button";
import { ArrowIcon } from "../../components/Icons";
import { SiteHeader } from "../../components/SiteHeader";
import { useSpyConfig } from "../../spy/useSpyConfig";
import { gameById, type Game } from "../select/games";
import { GUIDES, type Guide } from "./guides";
import { Quiz } from "./Quiz";
import { Scene } from "./Scene";
import styles from "./HowToPlay.module.css";

const TILT = [-2, 1.5, -1, 2];

/** #/how/<game>: the rules on one screen, a little play acted by the cast, and one question to try.
 * A game that isn't playable yet gets a teaser instead. */
export function HowToPlay({ gameId, onPlay }: { gameId: string; onPlay: (game: string) => void }) {
  const spyTitle = useSpyConfig()?.title ?? "";
  const game = gameById(gameId);
  if (!game) return null; // App only routes here for a known game
  const title = game.id === "out-of-place" ? spyTitle : game.title;
  const guide = game.playable ? GUIDES[game.id] : undefined;

  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <SiteHeader current="play" />
        <a href="#/" className={styles.back}>← All games</a>

        <header className={styles.hero}>
          <div className={styles.heroText}>
            <span className={`meta ${styles.eyebrow}`}>
              {guide ? `How to play · ${guide.minutes} min read` : "Coming soon"}
            </span>
            <h1 className={styles.title}>{title || "…"}</h1>
            <p className={styles.goal}>{guide?.goal ?? game.pitch}</p>
          </div>
          <Art game={game} />
        </header>

        {guide ? <Rules guide={guide} /> : <Teaser />}

        <footer className={styles.footer}>
          {game.playable ? (
            <Button variant="lantern" size="large" onClick={() => onPlay(game.id)} disabled={game.id === "out-of-place" && !spyTitle}>
              {game.cta} <ArrowIcon />
            </Button>
          ) : (
            <Button variant="lantern" size="large" onClick={() => onPlay("mafia")}>
              Play Mafia while you wait <ArrowIcon />
            </Button>
          )}
          <a href="#/" className={styles.footLink}>Back to games</a>
        </footer>
      </div>
    </div>
  );
}

function Art({ game }: { game: Game }) {
  return (
    <div className={styles.art} style={{ background: game.background }}>
      <svg viewBox="0 0 400 220" preserveAspectRatio="xMidYMax slice" aria-hidden="true">{game.scene}</svg>
    </div>
  );
}

function Section({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>
        <span className={`meta ${styles.num}`}>{String(n).padStart(2, "0")}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Rules({ guide }: { guide: Guide }) {
  return (
    <>
      <Section n={1} title="Who’s at the table">
        <ul className={styles.roles}>
          {guide.roles.map((r, i) => (
            <li key={r.name} className={`${styles.role} ${styles[r.tone]}`}
                style={{ "--tilt": `${TILT[i % TILT.length]}deg` } as React.CSSProperties}>
              <span className={styles.roleTop}>
                <strong className={styles.roleName}>{r.name}</strong>
                {r.count && <span className="meta">×{r.count}</span>}
              </span>
              <span className={styles.roleLine}>{r.line}</span>
            </li>
          ))}
        </ul>
        {guide.rolesNote && <p className={styles.note}>{guide.rolesNote}</p>}
      </Section>

      <Section n={2} title="How a round goes">
        <ol className={styles.steps}>
          {guide.steps.map((s, i) => (
            <li key={s.title} className={styles.step}>
              <span className={styles.stepNum}>{i + 1}</span>
              <strong className={styles.stepTitle}>{s.title}</strong>
              <span className={styles.stepLine}>{s.line}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section n={3} title="How it ends">
        <ul className={styles.ends}>
          {guide.ends.map((e) => (
            <li key={e.who} className={`${styles.end} ${styles[e.tone]}`}>
              <strong className={styles.endWho}>{e.who}</strong> {e.line}
            </li>
          ))}
        </ul>
      </Section>

      <Section n={4} title="Table tips">
        <ul className={styles.tips}>
          {guide.tips.map((t) => <li key={t}>{t}</li>)}
        </ul>
      </Section>

      <Section n={5} title={`Watch: ${guide.sceneTitle}`}>
        <Scene spec={guide.scene} label={guide.sceneTitle} />
      </Section>

      <Section n={6} title="Your turn">
        <Quiz spec={guide.quiz} />
      </Section>
    </>
  );
}

function Teaser() {
  return (
    <section className={styles.teaser}>
      <h2 className={styles.heading}>We’re still writing the rules for this table.</h2>
      <p className={styles.note}>
        Secret teams, public votes, and a hidden leader one side has to stop. The cast is already rehearsing.
      </p>
    </section>
  );
}
