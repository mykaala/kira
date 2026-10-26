import { useEffect, useRef, useState } from "react";
import { Toasts, type ToastItem } from "../../components/Toast";
import type { Mark, Marks } from "../../game/marks";
import { usePersisted } from "../../persisted";
import { nameOf, spySeats } from "../../spy/seats";
import type { SpyMove, SpyReveal, SpyStatus } from "../../spy/types";
import { useSpyConfig } from "../../spy/useSpyConfig";
import { post, useGame, type Speed } from "../../useGame";
import { Button } from "../../components/Button";
import { Review } from "../results/Review";
import { CenterPage } from "../game/GameScreen";
import pageStyles from "../game/GameScreen.module.css";
import { SpyDock, type MoveResult } from "./SpyDock";
import { SpyLog } from "./SpyLog";
import { SpyResults } from "./SpyResults";
import { SpySide } from "./SpySide";
import { LastChanceStage, QAStage, SpyVoteStage } from "./SpyStage";
import { SpyTable } from "./SpyTable";
import styles from "./SpyGame.module.css";

export const SPY_AUTO_KEY = "kira:spy-auto-advance";
const PHASE_LABEL: Record<string, string> = {
  deal: "Dealing",
  ask: "Questions",
  answer: "Questions",
  vote: "Vote",
  revote: "Revote",
  last_chance: "Last chance",
};

/** Out of Place, live: the table, the stage, the log and your secret; then the results and the review. */
export function SpyGameScreen({ gameId, onExit, onRematch, onSettings }: {
  gameId: string;
  onExit: () => void;
  onRematch: () => void;
  onSettings: () => void;
}) {
  const [speed, setSpeed] = usePersisted<Speed>("kira:pace", "slow");
  const [autoPref, setAutoPref] = usePersisted(SPY_AUTO_KEY, true);
  const { events, status, drafts, gone, failure, notices, revealData } = useGame<SpyStatus, SpyReveal>(gameId, speed);
  const [marks, setMarks] = usePersisted<Marks>(`kira:${gameId}:marks`, {});
  const [guess, setGuess] = useState("");
  const [voting, setVoting] = useState(false);
  const [votedIn, setVotedIn] = useState<string | null>(null); // the vote ("round:phase") the server took yours for
  const sending = useRef(false); // set synchronously, so a fast double click can't send two votes
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [view, setView] = useState<"table" | "results" | "review">("table");
  const [skipped, setSkipped] = useState(false); // voted out and skipped ahead: results as soon as they're in
  const toastId = useRef(0);

  const config = useSpyConfig();
  const over = (!!status?.over || skipped) && !!revealData;
  useEffect(() => {
    if (over) setView("results");
  }, [over]);
  useEffect(() => {
    document.title = status ? `${status.waiting_on_you ? "● Your turn · " : ""}${status.title} · Kira` : "Kira";
    return () => {
      document.title = "Kira";
    };
  }, [status?.waiting_on_you, status?.title]);

  const toast = (text: string, retry?: () => void) =>
    setToasts((t) => [...t.slice(-2), { id: ++toastId.current, text, retry }]);

  if (gone) {
    return (
      <CenterPage title="That game is gone." detail="It ended, or the server restarted, so it can't be rejoined.">
        <Button variant="lantern" onClick={onExit}>All games</Button>
      </CenterPage>
    );
  }
  if (!status) return <CenterPage title="Picking a place…" />;

  const seats = spySeats(status);
  if (over && view === "results") {
    return <SpyResults status={status} seats={seats} reveal={revealData!} marks={marks}
                       onReview={() => setView("review")} onRematch={onRematch} onSettings={onSettings} onExit={onExit} />;
  }
  if (over && view === "review") {
    return (
      <Review gameId={gameId} seats={seats.map((s) => ({ ...s, alive: true }))} events={revealData!.events} reveal={null}
              onBack={() => setView("results")}
              log={<SpyLog seats={seats} events={revealData!.events} title="Every question" tall />}
              side={<SpySide gameId={gameId} status={status} places={config?.places ?? []} onPickPlace={() => undefined} canGuess={false} />} />
    );
  }

  const move = async (m: SpyMove): Promise<MoveResult> => {
    try {
      await post(`/api/spy/games/${gameId}/move`, m);
      return { ok: true };
    } catch (e) {
      return { ok: false, ...parseError((e as Error).message) };
    }
  };
  const voteKey = `${status.round}:${status.phase}`;
  const vote = async (pid: string) => {
    if (sending.current) return;
    sending.current = true;
    setVoting(true);
    const r = await move({ type: "vote", target: pid });
    sending.current = false;
    setVoting(false);
    if (r.ok) setVotedIn(voteKey);
    else toast(r.error ?? "Your vote didn't go through.", () => vote(pid));
  };
  const call = (path: string, body: unknown = {}) =>
    post(`/api/games/${gameId}/${path}`, body).catch((e) => toast((e as Error).message, () => call(path, body)));
  const skip = () =>
    post(`/api/spy/games/${gameId}/skip`, {}).then(() => setSkipped(true)).catch((e) => toast((e as Error).message, skip));

  const typingPid = Object.keys(drafts)[0] ?? null;
  const speaking = typingPid ?? (status.phase === "ask" ? status.asker : status.phase === "answer" ? status.answerer : null);
  const turnLine = status.waiting_on_you
    ? "Your turn"
    : status.phase === "ask" ? `${nameOf(seats, status.asker)} is asking`
      : status.phase === "answer" ? `${nameOf(seats, status.answerer)} is answering`
        : status.phase === "vote" || status.phase === "revote" ? "Everyone votes"
          : status.phase === "last_chance" ? "The spy is guessing" : "";
  const canGuess = !!status.turn && (status.turn.can_guess || status.turn.type === "last_chance");
  const shownNotices = Array.from(new Set([...status.notices, ...notices]));

  let stage: React.ReactNode;
  if (status.phase === "vote" || status.phase === "revote") {
    stage = <SpyVoteStage status={status} seats={seats} events={events} onVote={vote} busy={voting}
                          voted={votedIn === voteKey} />;
  } else if (status.phase === "last_chance") {
    stage = <LastChanceStage status={status} seats={seats} />;
  } else {
    stage = <QAStage status={status} seats={seats} events={events} drafts={drafts} />;
  }

  return (
    <div className="lantern-page">
      <div className={pageStyles.page}>
        <header className={styles.bar}>
          <div className={styles.barTitle}>
            <span className={styles.barName}>{status.title}</span>
            <span className={`meta ${styles.barPhase}`}>
              {status.survive_votes > 1 ? `Round ${status.round} · ` : ""}{PHASE_LABEL[status.phase] ?? status.phase}
              {status.phase === "ask" || status.phase === "answer" ? ` · ${status.questions} of ${status.questions_total} asked` : ""}
            </span>
            {status.survive_votes > 1 && (
              <span className={`meta ${styles.barSurvived}`}>
                The spy has survived {status.votes_survived} of {status.survive_votes} votes
              </span>
            )}
          </div>
          <span className={`${styles.barTurn} ${status.waiting_on_you ? styles.barTurnYou : ""}`} aria-live="polite">{turnLine}</span>
          <span className={styles.secretChip} aria-label="Your secret">
            {"place" in status.secret ? <>The place: <strong>{status.secret.place}</strong></> : <strong>You're the spy</strong>}
          </span>
          <div className={styles.pace}>
            <label className={styles.toggle} title="Let the AI players go without waiting for you">
              <input type="checkbox" checked={autoPref} onChange={(e) => { setAutoPref(e.target.checked); call("pace", { auto: e.target.checked }); }} />
              Auto
            </label>
            <label className={styles.toggle} title="How fast lines type out and votes are revealed">
              Pace
              <select value={speed} onChange={(e) => setSpeed(e.target.value as Speed)}>
                <option value="slow">Slow</option>
                <option value="normal">Normal</option>
                <option value="fast">Fast</option>
              </select>
            </label>
          </div>
        </header>
        {failure && (
          <div className={pageStyles.failure} role="alert">
            <span>{failure}</span>
            <Button variant="lantern" size="small" onClick={onExit}>All games</Button>
          </div>
        )}
        {shownNotices.length > 0 && (
          <div className={styles.notices} role="status">
            {shownNotices.slice(-3).map((n) => <div key={n} className={styles.notice}>{n}</div>)}
          </div>
        )}
        <SpyTable seats={seats} speaking={speaking} asked={status.asked} answered={status.answered} marks={marks}
                  onMark={(pid: string, m: Mark) => setMarks((all) => ({ ...all, [pid]: m }))} />
        <div className={pageStyles.columns}>
          <main className={pageStyles.main}>
            {stage}
            {status.ghost ? (
              <div className={styles.dock} role="status">
                <p className={styles.turnNote}>You were voted out, so you're watching now. You still know the place.</p>
                <div className={styles.dockRow}>
                  <span className={styles.muted}>{skipped ? "Skipping ahead…" : "The others play on without you."}</span>
                  {status.waiting_for_next && !skipped && <Button variant="surface" onClick={() => call("next")}>Next ▸</Button>}
                  <Button variant="surface" onClick={skip} disabled={skipped}>Skip to the end</Button>
                </div>
              </div>
            ) : (
              <SpyDock status={status} seats={seats} guess={guess} onGuess={setGuess} onMove={move}
                       onNext={() => call("next")} />
            )}
            <SpyLog seats={seats} events={events} />
          </main>
          <SpySide gameId={gameId} status={status} places={config?.places ?? []} canGuess={canGuess}
                   onPickPlace={(p) => setGuess(p)} />
        </div>
      </div>
      <Toasts items={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  );
}

/** post() throws the server's detail as its message; a soft warning's detail is an object. */
function parseError(msg: string): { warning?: string; error?: string } {
  try {
    const d = JSON.parse(msg);
    if (d && typeof d === "object" && d.warning) return { warning: d.warning };
  } catch {
    // a plain message
  }
  return { error: msg };
}
