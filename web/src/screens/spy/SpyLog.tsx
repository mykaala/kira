import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { nameOf, type SpySeat } from "../../spy/seats";
import type { GameEvent } from "../../types";
import styles from "../game/ChatLog.module.css";

const SHOWN = new Set(["first", "ask", "answer", "accused", "survived", "guess", "last_guess", "outcome", "info"]);
const NEAR_BOTTOM_PX = 48;

/** Every question and answer in one scrolling log. Follows new lines only while you're at the bottom. */
export function SpyLog({ seats, events, title = "Questions so far", tall = false }: {
  seats: SpySeat[];
  events: GameEvent[];
  title?: string;
  tall?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);
  const lines = events.filter((e) => SHOWN.has(e.kind));
  const asked = lines.filter((e) => e.kind === "ask").length;
  const who = (pid: string | null) => nameOf(seats, pid);
  const colour = (pid: string | null) => {
    const s = seats.find((x) => x.id === pid);
    return s?.character ? `var(--c-${s.character})` : "var(--lantern)";
  };

  useLayoutEffect(() => {
    if (following && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines.length, following]);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onScroll = () => setFollowing(el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <section className={`${styles.chat} ${tall ? styles.tall : ""}`} aria-label="Questions and answers">
      <div className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        <span className={`meta ${styles.count}`}>{asked} {asked === 1 ? "question" : "questions"}</span>
      </div>
      <div ref={box} className={styles.lines} aria-live="off" tabIndex={0}>
        {lines.length === 0 && <p className={styles.empty}>No questions yet.</p>}
        {lines.map((e) =>
          e.kind === "ask" || e.kind === "answer" ? (
            <div key={e.seq} className={styles.line}>
              <span className={styles.dot} style={{ background: colour(e.actor) }} />
              <p className={styles.body}>
                <strong>{who(e.actor)}</strong>
                {e.kind === "ask" ? <> {who(e.actor) === "You" ? "ask" : "asks"} <strong>{who(e.target)}</strong>:</> : ":"}{" "}
                <span className={styles.said}>{e.text}</span>
              </p>
            </div>
          ) : (
            <div key={e.seq} className={styles.sys}>
              <span className={e.kind === "outcome" || e.kind === "accused" ? styles.sysStrong : ""}>{e.text}</span>
            </div>
          ),
        )}
      </div>
      {!following && (
        <button type="button" className={styles.jump}
                onClick={() => box.current?.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" })}>
          ↓ Latest
        </button>
      )}
    </section>
  );
}
