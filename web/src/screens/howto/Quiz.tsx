import { useState } from "react";
import type { CharacterId } from "../../cast";
import { Portrait } from "../../components/Portrait";
import styles from "./Quiz.module.css";

export type QuizSpec = {
  title: string;
  setup: { label: string; value: string };
  question: string;
  answers: { who: CharacterId; name: string; text: string; right?: boolean; why: string }[];
};

/** One question, a handful of lines from the cast, tap the one that gives it away. Wrong picks explain
 * themselves and stay open, so the viewer can keep looking. */
export function Quiz({ spec }: { spec: QuizSpec }) {
  const [picked, setPicked] = useState<CharacterId[]>([]);
  const solved = spec.answers.some((a) => a.right && picked.includes(a.who));

  return (
    <div className={styles.quiz}>
      <div className={styles.head}>
        <h3 className={styles.title}>{spec.title}</h3>
        <span className={styles.setup}>
          <span className="meta">{spec.setup.label}</span> <strong>{spec.setup.value}</strong>
        </span>
      </div>
      <p className={styles.question}>{spec.question}</p>
      <ul className={styles.answers}>
        {spec.answers.map((a) => {
          const shown = picked.includes(a.who);
          const state = shown ? (a.right ? styles.right : styles.wrong) : "";
          return (
            <li key={a.who}>
              <button type="button" className={`${styles.answer} ${state}`} disabled={solved || shown}
                      onClick={() => setPicked((p) => [...p, a.who])}>
                <Portrait character={a.who} size={48} mood={shown && a.right ? "angry" : "neutral"} />
                <span className={styles.words}>
                  <strong>{a.name}</strong>
                  <span>“{a.text}”</span>
                  {shown && <span className={styles.why} role="status">{a.right ? "Got it. " : "Not this one. "}{a.why}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {picked.length > 0 && (
        <button type="button" className={styles.again} onClick={() => setPicked([])}>Try again</button>
      )}
    </div>
  );
}
