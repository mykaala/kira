import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Seat } from "../../game/model";
import type { GameEvent } from "../../types";
import styles from "./ChatLog.module.css";

const SHOWN = new Set(["say", "morning", "elimination", "vote", "result", "mafia_choice"]);
const NEAR_BOTTOM_PX = 48;

/** The running chat for the whole game, with day dividers. The newest message is on the stage
 * above, so it joins the chat once the next one arrives. Follows new lines only while you're
 * at the bottom, so reading back doesn't jump. ★ pins a line to your notes. */
export function ChatLog({ seats, events, hideSeq, pinned, onPin, title = "The chat", tall = false }: {
  seats: Seat[];
  events: GameEvent[];
  hideSeq?: number | null; // the line currently on stage
  pinned: number[];
  onPin: (e: GameEvent, who: string) => void;
  title?: string;
  tall?: boolean; // review: use the page height
}) {
  const box = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);
  const seat = (pid: string | null) => seats.find((s) => s.id === pid);
  const nameOf = (pid: string | null) => {
    const s = seat(pid);
    return s ? (s.you ? "You" : s.name) : "?";
  };

  const lines = events.filter((e) => SHOWN.has(e.kind) && e.seq !== hideSeq);
  const said = lines.filter((e) => e.kind === "say").length;

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

  let lastDay = -1;
  return (
    <section className={`${styles.chat} ${tall ? styles.tall : ""}`} aria-label="The chat so far">
      <div className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        <span className={`meta ${styles.count}`}>{said} {said === 1 ? "line" : "lines"}</span>
      </div>
      <div ref={box} className={styles.lines} aria-live="off">
        {lines.length === 0 && <p className={styles.empty}>Nobody has said anything yet.</p>}
        {lines.flatMap((e) => {
          const rule = e.day !== lastDay ? <div key={`day-${e.day}`} className={`meta ${styles.dayRule}`}>Day {e.day}</div> : null;
          lastDay = e.day;
          return [rule, <Line key={e.seq} e={e} seat={seat(e.actor)} nameOf={nameOf} pinned={pinned.includes(e.seq)}
                              onPin={() => onPin(e, nameOf(e.actor))} />];
        })}
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

function Line({ e, seat, nameOf, pinned, onPin }: {
  e: GameEvent;
  seat?: Seat;
  nameOf: (pid: string | null) => string;
  pinned: boolean;
  onPin: () => void;
}) {
  if (e.kind === "say") {
    return (
      <div className={`${styles.line} ${pinned ? styles.pinned : ""}`}>
        <span className={styles.dot} style={{ background: seat?.character ? `var(--c-${seat.character})` : "var(--lantern)" }} />
        <p className={styles.body}>
          <strong>{nameOf(e.actor)}</strong> <span className={styles.said}>{e.text}</span>
          {pinned && <span className={styles.pinNote}>★ pinned to your notes</span>}
        </p>
        <button type="button" className={styles.pin} onClick={onPin}
                aria-label={pinned ? "Unpin from your notes" : "Pin to your notes"} aria-pressed={pinned}>★</button>
      </div>
    );
  }
  const secret = e.vis !== "public";
  const owner = e.vis.startsWith("private:") ? e.vis.slice(8) : null;
  return (
    <div className={styles.sys}>
      {secret && <span className={styles.secretTag}>{owner ? `${nameOf(owner)} only · ` : "Mafia only · "}</span>}
      <span className={e.kind === "morning" || e.kind === "elimination" ? styles.sysStrong : secret ? styles.secretLine : ""}>
        {e.text}
      </span>
    </div>
  );
}
