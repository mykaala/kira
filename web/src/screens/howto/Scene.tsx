import { useEffect, useRef, useState } from "react";
import type { CharacterId } from "../../cast";
import { Portrait, type Mood } from "../../components/Portrait";
import styles from "./Scene.module.css";

export type Tone = "coral" | "teal" | "lavender" | "lantern" | "paper";
export type Tag = { text: string; tone: Tone };

/** One moment of a scene. Anything left out is back to rest: neutral faces, no tags, no votes. */
export type Beat = {
  ms: number;
  phase: string;
  caption: string;
  night?: boolean;
  moods?: Partial<Record<CharacterId, Mood>>;
  say?: { who: CharacterId; text: string; think?: boolean };
  tags?: Partial<Record<CharacterId, Tag>>;
  votes?: Partial<Record<CharacterId, number>>;
  look?: CharacterId; // everyone else turns towards this player
  card?: { label: string; value: string; tone: Tone }; // the corner card: what this view knows
  views?: Record<string, Partial<Omit<Beat, "views">>>;
};

export type SceneSpec = {
  cast: CharacterId[];
  names: Partial<Record<CharacterId, string>>;
  beats: Beat[];
  views?: { id: string; label: string }[];
};

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** A looping, captioned little play acted by the cast. Starts when it scrolls into view; with reduced
 * motion it waits for the viewer to step through it. */
export function Scene({ spec, label }: { spec: SceneSpec; label: string }) {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [view, setView] = useState(spec.views?.[0].id);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (reducedMotion()) return;
    const seen = new IntersectionObserver(([e]) => setPlaying(e.isIntersecting), { threshold: 0.4 });
    if (root.current) seen.observe(root.current);
    return () => seen.disconnect();
  }, []);

  const base = spec.beats[i];
  const beat: Beat = { ...base, ...(view && base.views?.[view]) };

  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setI((n) => (n + 1) % spec.beats.length), beat.ms);
    return () => clearTimeout(t);
  }, [playing, i, beat.ms, spec.beats.length]);

  const n = spec.cast.length;
  const look = beat.look ? spec.cast.indexOf(beat.look) : -1;
  const speaker = beat.say ? spec.cast.indexOf(beat.say.who) : -1;

  return (
    <figure className={styles.scene} ref={root} aria-label={label}>
      <div className={`${styles.stage} ${beat.night ? styles.night : ""}`}>
        {beat.card && (
          <div key={`${view}-${beat.card.value}`} className={`${styles.known} ${styles[beat.card.tone]}`}>
            <span className="meta">{beat.card.label}</span>
            <strong>{beat.card.value}</strong>
          </div>
        )}
        <div className={styles.talk}>
          {beat.say && (
            <div key={`${i}-${view}`} className={`${styles.bubble} ${beat.say.think ? styles.think : ""}`}
                 style={{ "--at": `${((speaker + 0.5) / n) * 100}%` } as React.CSSProperties}>
              <span className="visually-hidden">{spec.names[beat.say.who]} {beat.say.think ? "thinks" : "says"}: </span>
              {beat.say.text}
            </div>
          )}
        </div>
        <ol className={styles.seats} style={{ "--n": n } as React.CSSProperties}>
          {spec.cast.map((c, k) => {
            const mood = beat.moods?.[c] ?? (speaker === k && !beat.say?.think ? "speaking" : "neutral");
            const lean = look < 0 || k === look ? 0 : k < look ? 1 : -1;
            const tag = beat.tags?.[c];
            const votes = beat.votes?.[c] ?? 0;
            return (
              <li key={c} className={`${styles.seat} ${speaker === k ? styles.speaking : ""}`}
                  style={{ "--lean": lean } as React.CSSProperties}>
                <span className={styles.tagSlot}>
                  {tag && <span key={tag.text} className={`${styles.tag} ${styles[tag.tone]}`}>{tag.text}</span>}
                </span>
                <span className={styles.face}><Portrait character={c} mood={mood} size="fill" /></span>
                <span className={styles.name}>{spec.names[c]}</span>
                <span className={styles.votes} aria-label={votes ? `${votes} votes` : undefined}>
                  {Array.from({ length: votes }, (_, v) => (
                    <span key={v} className={styles.vote} style={{ animationDelay: `${v * 90}ms` }} />
                  ))}
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      <figcaption className={styles.caption}>
        <span className={`meta ${styles.phase}`}>{beat.phase}</span>
        <span key={`${i}-${view}`} className={styles.captionText}>{beat.caption}</span>
      </figcaption>

      <div className={styles.controls}>
        <button type="button" className={styles.ctl} onClick={() => setPlaying((p) => !p)}
                aria-label={playing ? "Pause" : "Play"}>
          {playing ? "❚❚" : "▶"}
        </button>
        <div className={styles.dots}>
          {spec.beats.map((b, k) => (
            <button key={k} type="button" className={`${styles.dot} ${k === i ? styles.on : ""}`}
                    aria-label={`Step ${k + 1}: ${b.phase}`} aria-current={k === i ? "step" : undefined}
                    onClick={() => setI(k)} />
          ))}
        </div>
        {spec.views && (
          <div className={styles.views} role="group" aria-label="Whose eyes">
            {spec.views.map((v) => (
              <button key={v.id} type="button" className={`${styles.view} ${v.id === view ? styles.picked : ""}`}
                      aria-pressed={v.id === view} onClick={() => setView(v.id)}>
                {v.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </figure>
  );
}
