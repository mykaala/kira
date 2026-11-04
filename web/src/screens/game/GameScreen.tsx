import { useEffect, useState } from "react";
import { Button } from "../../components/Button";
import { LanternMark } from "../../components/LanternMark";
import type { Marks, Mark } from "../../game/marks";
import { namedIn, replyingTo, rolesInPlay, seatsOf, stageLine } from "../../game/model";
import { reactionFor } from "../../game/reactions";
import { usePersisted } from "../../persisted";
import type { GameEvent } from "../../types";
import { useCast } from "../../useCast";
import { post, useGame, type Playback } from "../../useGame";
import { Results } from "../results/Results";
import { Review } from "../results/Review";
import { ActionDock, SpectatorDock } from "./ActionDock";
import { PhaseBar } from "./PhaseBar";
import { AnnouncementStage, NightStage, VoteTray } from "./Stage";
import { TableStrip } from "./TableStrip";
import { ChatLog } from "./ChatLog";
import { ControlCenter, useNotes } from "./Notes";
import styles from "./GameScreen.module.css";

const MAX_REACTIONS = 3;
// how long a finished line stays the newest before the next one starts: 3.5 s, more for long lines, a little jitter
const MIN_DWELL_MS = 3500;
const MAX_DWELL_MS = 9000;
const SHORT_LINE = 80; // characters
const MS_PER_EXTRA_CHAR = 30;
const JITTER_MS = 1000;

const PLAYBACK: Playback = {
  holdTyping: true,
  dwell: (e: GameEvent) => {
    if (e.kind !== "say" || !e.text) return undefined;
    const read = MIN_DWELL_MS + Math.max(0, e.text.length - SHORT_LINE) * MS_PER_EXTRA_CHAR;
    return Math.min(MAX_DWELL_MS, read) + Math.random() * JITTER_MS;
  },
};

const typingInto = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(t.tagName));

/** A game from first night to the results: the live table, then results and review. */
export function GameScreen({ gameId, onExit, onRematch }: {
  gameId: string;
  onExit: () => void;
  onRematch: () => void;
}) {
  const { notes, setNotes, pinned, pin } = useNotes(gameId);
  const [notesOpen, setNotesOpen] = usePersisted(`kira:${gameId}:notes-open`, false);
  const [paused, setPaused] = useState(false);
  const { events, status, drafts, acted, reveal, gone, failure, serverWaiting, backlog } =
    useGame(gameId, "normal", PLAYBACK);
  const [marks, setMarks] = usePersisted<Marks>(`kira:${gameId}:marks`, {});
  const cast = useCast();
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<{ key: string; pid: string } | null>(null);
  const [view, setView] = useState<"table" | "results" | "review">("table");

  const [, setLastCast] = usePersisted<string[]>("kira:last-cast", []);
  const winner = status?.winner;
  const serverAuto = status?.auto;
  useEffect(() => {
    // the server runs ahead on its own in auto mode (games started before Pause existed): take the wheel back
    if (serverAuto) post(`/api/games/${gameId}/pace`, { auto: false }).catch(() => undefined);
  }, [serverAuto, gameId]);
  useEffect(() => {
    // ask for the next voice once nothing typed is queued: the server stays one line ahead of what you've read
    if (serverWaiting && !paused && backlog === 0 && !winner) {
      post(`/api/games/${gameId}/next`, {}).catch(() => undefined);
    }
  }, [serverWaiting, paused, backlog, winner, gameId]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== " " || e.repeat || typingInto(e.target)) return;
      e.preventDefault();
      setPaused((p) => !p);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (winner) setView("results");
  }, [winner]);
  const castKey = status ? Object.values(status.characters ?? {}).join(",") : "";
  useEffect(() => {
    if (castKey) setLastCast(castKey.split(",")); // faces for the "pick up where you left off" strip
  }, [castKey, setLastCast]);

  if (gone) {
    return (
      <CenterPage title="That game is gone." detail="It ended, or the server restarted, so it can't be rejoined.">
        <Button variant="lantern" onClick={onExit}>New game</Button>
      </CenterPage>
    );
  }
  if (!status) return <CenterPage title="Lighting the lantern…" />;

  const seats = seatsOf(status);
  const me = seats.find((s) => s.you)!;

  if (winner && view === "results") {
    return <Results status={status} seats={seats} events={reveal ?? events} cast={cast} marks={marks}
                    onReview={() => setView("review")} onRematch={onRematch} onExit={onExit} />;
  }
  if (winner && view === "review") {
    return <Review gameId={gameId} status={status} seats={seats} events={events} reveal={reveal}
                   onBack={() => setView("results")} />;
  }

  const call = async (path: string, body: unknown = {}) => {
    setError("");
    try {
      await post(`/api/games/${gameId}/${path}`, body);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    }
  };
  const phaseKey = `${status.day}:${status.phase}`;
  const myPick = picked?.key === phaseKey ? picked.pid : null;
  const pick = async (pid: string) => {
    if (await call("action", { action: pid })) setPicked({ key: phaseKey, pid });
  };

  const discussion = status.phase === "discussion";
  const line = discussion ? stageLine(events, drafts, status.day) : null;
  const nextName = status.next_speaker ? seats.find((s) => s.id === status.next_speaker)?.name ?? null : null;
  const morning = [...events].reverse().find((e) => e.kind === "morning" && e.day === status.day);
  const about = line ? replyingTo(line, events, seats, status.day) : null;
  // whoever the finished line names reacts on their chip
  const reactions: Record<string, string> = {};
  if (line && !line.typing) {
    for (const pid of namedIn(line.text, seats, line.pid).slice(0, MAX_REACTIONS)) {
      const s = seats.find((x) => x.id === pid);
      if (s?.alive && s.character) reactions[pid] = reactionFor(s.character, (line.seq ?? 0) + pid.length);
    }
  }

  // the big banner only for news and decisions: night, the vote, and the morning before anyone speaks
  let banner: React.ReactNode = null;
  if (status.phase === "night") {
    banner = <NightStage status={status} seats={seats} picked={myPick} onPick={pick}
                         onSkip={() => pick("abstain")} />;
  } else if (status.phase === "vote") {
    banner = <VoteTray status={status} seats={seats} events={events} voted={myPick} onVote={pick} />;
  } else if (!line) {
    banner = (
      <AnnouncementStage compact
        kicker={`Day ${status.day} · Morning`}
        headline={morning?.text ?? "Morning comes."}
        detail={status.waiting_on_you ? "You open the talk." : nextName ? `${nextName} speaks first.` : undefined}
      />
    );
  }

  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <PhaseBar status={status} />
        {failure && (
          <div className={styles.failure} role="alert">
            <span>{failure}</span>
            <Button variant="lantern" size="small" onClick={onExit}>New game</Button>
          </div>
        )}
        <TableStrip seats={seats} speaking={line?.pid ?? null} typing={!!line?.typing}
                    leanings={status.accusations ?? {}} reactions={reactions} reactKey={line?.seq ?? null}
                    acted={acted} phase={status.phase} marks={marks} guesses={rolesInPlay(status)}
                    onMark={(pid: string, m: Mark) => setMarks((all) => ({ ...all, [pid]: m }))} />
        <div className={styles.columns}>
          <main className={styles.main}>
            {banner}
            <ChatLog seats={seats} events={events} pinned={pinned} onPin={pin} fill paused={paused}
                     live={line ? { line, about: seats.find((s) => s.id === about) } : null} />
            {me.alive ? (
              <ActionDock status={status} error={error} seats={seats}
                          onSay={(text, accuses) => call("say", { text, accuses })} onPass={() => call("pass")} />
            ) : (
              <SpectatorDock />
            )}
          </main>
          <ControlCenter
            paused={paused} onPause={() => setPaused((p) => !p)}
            canCallVote={discussion && me.alive} onCallVote={() => call("call-vote")}
            open={notesOpen} onOpen={setNotesOpen}
            status={status} seats={seats} events={events}
            notes={notes} onNotes={setNotes} pinned={pinned} onPin={pin}
            marks={marks} guesses={rolesInPlay(status)}
            onMark={(pid: string, m: Mark) => setMarks((all) => ({ ...all, [pid]: m }))}
          />
        </div>
      </div>
    </div>
  );
}

export function CenterPage({ title, detail, children }: { title: string; detail?: string; children?: React.ReactNode }) {
  return (
    <div className="lantern-page">
      <div className={styles.centerPage}>
        <div className={styles.centerInner}>
          <LanternMark size={44} />
          <h1 className={styles.bigTitle}>{title}</h1>
          {detail && <p className={styles.soft}>{detail}</p>}
          {children}
        </div>
      </div>
    </div>
  );
}
