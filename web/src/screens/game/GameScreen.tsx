import { useEffect, useState } from "react";
import { Button } from "../../components/Button";
import { LanternMark } from "../../components/LanternMark";
import type { Marks, Mark } from "../../game/marks";
import { rolesInPlay, seatsOf, stageLine } from "../../game/model";
import { usePersisted } from "../../persisted";
import { useCast } from "../../useCast";
import { post, useGame, type Speed } from "../../useGame";
import { Results } from "../results/Results";
import { Review } from "../results/Review";
import { ActionDock, SpectatorDock } from "./ActionDock";
import { PhaseBar } from "./PhaseBar";
import { AnnouncementStage, NightStage, SpeechStage, VoteTray } from "./Stage";
import { TableStrip } from "./TableStrip";
import { ChatLog } from "./ChatLog";
import { NotesPanel, useNotes } from "./Notes";
import styles from "./GameScreen.module.css";

export const AUTO_KEY = "kira:auto-advance";

/** A game from first night to the results: the live table, then results and review. */
export function GameScreen({ gameId, onExit, onRematch }: {
  gameId: string;
  onExit: () => void;
  onRematch: () => void;
}) {
  // new keys so the new defaults (slow, auto-advance on) apply even where old defaults were saved
  const [speed, setSpeed] = usePersisted<Speed>("kira:pace", "slow");
  const [autoPref, setAutoPref] = usePersisted(AUTO_KEY, true);
  const { notes, setNotes, pinned, pin } = useNotes(gameId);
  const { events, status, drafts, acted, reveal, gone, failure } = useGame(gameId, speed);
  const [marks, setMarks] = usePersisted<Marks>(`kira:${gameId}:marks`, {});
  const cast = useCast();
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<{ key: string; pid: string } | null>(null);
  const [view, setView] = useState<"table" | "results" | "review">("table");

  const [, setLastCast] = usePersisted<string[]>("kira:last-cast", []);
  const winner = status?.winner;
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

  let stage: React.ReactNode;
  if (status.phase === "night") {
    stage = <NightStage status={status} seats={seats} picked={myPick} onPick={pick}
                        onSkip={() => pick("abstain")} />;
  } else if (status.phase === "vote") {
    stage = <VoteTray status={status} seats={seats} events={events} voted={myPick} onVote={pick} />;
  } else if (line) {
    stage = <SpeechStage line={line} seats={seats} events={events} day={status.day} />;
  } else {
    stage = (
      <AnnouncementStage
        kicker={`Day ${status.day} · Morning`}
        headline={morning?.text ?? "Morning comes."}
        detail={status.waiting_on_you ? "You open the talk." : nextName ? `${nextName} speaks first.` : undefined}
      />
    );
  }

  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <PhaseBar
          status={status}
          canCallVote={discussion && me.alive}
          onCallVote={() => call("call-vote")}
          auto={autoPref}
          onAuto={(on) => {
            setAutoPref(on);
            call("pace", { auto: on });
          }}
          speed={speed}
          onSpeed={setSpeed}
        />
        {failure && (
          <div className={styles.failure} role="alert">
            <span>{failure}</span>
            <Button variant="lantern" size="small" onClick={onExit}>New game</Button>
          </div>
        )}
        <TableStrip seats={seats} speaking={line?.pid ?? null} leanings={status.accusations ?? {}}
                    acted={acted} phase={status.phase} marks={marks} guesses={rolesInPlay(status)}
                    onMark={(pid: string, m: Mark) => setMarks((all) => ({ ...all, [pid]: m }))} />
        <div className={styles.columns}>
          <main className={styles.main}>
            {stage}
            <ChatLog seats={seats} events={events} hideSeq={line && !line.typing ? line.seq : null}
                     pinned={pinned} onPin={pin} />
            {me.alive ? (
              <ActionDock status={status} seats={seats} nextName={nextName} error={error} busy={!!line?.typing}
                          onSay={(text, accuses) => call("say", { text, accuses })} onNext={() => call("next")}
                          onPass={() => call("pass")} />
            ) : (
              <SpectatorDock canNext={discussion && status.waiting_for_next && !line?.typing} nextName={nextName}
                             onNext={() => call("next")} />
            )}
          </main>
          <NotesPanel notes={notes} onNotes={setNotes} status={status} seats={seats} events={events} />
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
