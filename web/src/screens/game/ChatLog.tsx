import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Portrait } from "../../components/Portrait";
import { moodOf, type Seat, type StageLine } from "../../game/model";
import type { GameEvent } from "../../types";
import styles from "./ChatLog.module.css";

const SHOWN = new Set(["say", "morning", "elimination", "vote", "result", "mafia_choice"]);
const NEAR_BOTTOM_PX = 48;

/** The running chat for the whole game, with day dividers. The live line (the one being typed, or the
 * newest one said) sits highlighted at the bottom and joins the chat once the next one starts. Follows new
 * lines only while you're at the bottom, so reading back doesn't jump. ★ pins a line to your notes. */
export function ChatLog({ seats, events, live, pinned, onPin, paused, title = "The chat", tall = false, fill = false }: {
  seats: Seat[];
  events: GameEvent[];
  live?: { line: StageLine; about?: Seat } | null;
  pinned: number[];
  onPin: (e: GameEvent, who: string) => void;
  paused?: boolean;
  title?: string;
  tall?: boolean; // review: use the page height
  fill?: boolean; // live table: take the column's leftover height
}) {
  const box = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);
  const seat = (pid: string | null) => seats.find((s) => s.id === pid);
  const nameOf = (pid: string | null) => {
    const s = seat(pid);
    return s ? (s.you ? "You" : s.name) : "?";
  };

  const liveSeq = live && !live.line.typing ? live.line.seq : null;
  const lines = events.filter((e) => SHOWN.has(e.kind) && e.seq !== liveSeq);
  const said = events.filter((e) => e.kind === "say").length;
  const liveEvent = liveSeq !== null ? events.find((e) => e.seq === liveSeq) : undefined;

  useLayoutEffect(() => {
    if (following && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines.length, following, live?.line.text, live?.line.pid]);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onScroll = () => setFollowing(el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  let lastDay = -1;
  return (
    <section className={`${styles.chat} ${tall ? styles.tall : ""} ${fill ? styles.fill : ""}`} aria-label="The chat so far">
      <div className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        {paused && <span className={`meta ${styles.pausedChip}`}>Paused</span>}
        <span className={`meta ${styles.count}`}>{said} {said === 1 ? "line" : "lines"}</span>
      </div>
      <div ref={box} className={styles.lines} aria-live="off">
        {lines.length === 0 && !live && <p className={styles.empty}>Nobody has said anything yet.</p>}
        {lines.flatMap((e) => {
          const rule = e.day !== lastDay ? <div key={`day-${e.day}`} className={`meta ${styles.dayRule}`}>Day {e.day}</div> : null;
          lastDay = e.day;
          return [rule, <Line key={e.seq} e={e} seat={seat(e.actor)} nameOf={nameOf} pinned={pinned.includes(e.seq)}
                              onPin={() => onPin(e, nameOf(e.actor))} />];
        })}
        {live && (
          <LiveLine line={live.line} seat={seat(live.line.pid)} about={live.about}
                    pinned={liveSeq !== null && pinned.includes(liveSeq)}
                    onPin={liveEvent ? () => onPin(liveEvent, nameOf(liveEvent.actor)) : undefined} />
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

/** The newest line, big: who's talking, whom they answer, the words as they type out. */
function LiveLine({ line, seat, about, pinned, onPin }: {
  line: StageLine;
  seat?: Seat;
  about?: Seat;
  pinned: boolean;
  onPin?: () => void;
}) {
  return (
    <div className={`${styles.live} ${line.typing ? styles.liveTyping : ""}`}>
      {seat?.character ? (
        <Portrait character={seat.character} mood={moodOf(line)} size={52} className={styles.liveFace} />
      ) : (
        <span className={styles.liveYou}>You</span>
      )}
      <div className={styles.liveBody}>
        <div className={styles.liveHead}>
          {/* no voice label here: during a game it would hint at how they think */}
          <strong style={{ color: seat?.character ? `var(--c-${seat.character})` : "var(--lantern)" }}>
            {seat?.you ? "You" : seat?.name ?? "?"}
          </strong>
          {about && (
            <span className={styles.replying}>
              {about.character && <Portrait character={about.character} size={20} />}
              replying to {about.you ? "you" : about.name}
            </span>
          )}
        </div>
        <p className={styles.liveWords} aria-live="polite">{line.text || " "}</p>
        {line.typing && (
          <div className={styles.dots} aria-label="still talking">
            <span /><span /><span />
          </div>
        )}
      </div>
      {onPin && (
        <button type="button" className={`${styles.pin} ${pinned ? styles.pinOn : ""}`} onClick={onPin}
                aria-label={pinned ? "Unpin from your notes" : "Pin to your notes"} aria-pressed={pinned}>★</button>
      )}
    </div>
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
