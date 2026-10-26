import { Portrait } from "../../components/Portrait";
import type { Seat } from "../../game/model";
import { nameOf, type SpySeat } from "../../spy/seats";
import type { SpyStatus } from "../../spy/types";
import type { GameEvent } from "../../types";
import { AnnouncementStage, Frame, PickTray } from "../game/Stage";
import styles from "./SpyGame.module.css";

const asSeat = (s: SpySeat): Seat => ({ ...s });

function Speaker({ seat, children, typing }: { seat?: SpySeat; children: React.ReactNode; typing?: boolean }) {
  return (
    <div className={styles.qaRow}>
      {seat?.character ? (
        <Portrait character={seat.character} mood={typing ? "speaking" : "neutral"} size={72} shape="rounded" />
      ) : (
        <span className={styles.youTile}>You</span>
      )}
      <div className={styles.bubble}>{children}</div>
    </div>
  );
}

/** The latest question and its answer, big; a line still being "typed" shows as it arrives. */
export function QAStage({ status, seats, events, drafts }: {
  status: SpyStatus;
  seats: SpySeat[];
  events: GameEvent[];
  drafts: Record<string, string>;
}) {
  const seat = (pid: string | null) => seats.find((s) => s.id === pid);
  const first = [...events].reverse().find((e) => e.kind === "first"); // opens the current round
  const asks = events.filter((e) => e.kind === "ask" && (!first || e.seq > first.seq));
  const q = asks[asks.length - 1];
  const a = q && events.find((e) => e.kind === "answer" && e.seq > q.seq);
  const typing = Object.entries(drafts)[0]; // [pid, text so far]
  const asking = typing && (!q || a || typing[0] !== q.target) ? typing : null; // a new question under way
  const answering = typing && q && !a && typing[0] === q.target ? typing : null;

  if (!q && !asking) {
    const k = status.survive_votes;
    const detail = status.round === 1
      ? `Everyone asks one question. Then the vote.${k > 1 ? ` The spy wins after surviving ${k} votes.` : ""}`
      : `The spy has survived ${status.votes_survived} of ${k} votes. Everyone still in asks one question, then vote again.`;
    return (
      <AnnouncementStage kicker={`${status.title} · Round ${status.round}`}
                         headline={first ? first.text.replace(/^Round \d+\. /, "") : "Picking a place…"} detail={detail} />
    );
  }
  const shownQ = asking
    ? { actor: asking[0], target: null as string | null, text: asking[1], typing: true }
    : { actor: q!.actor, target: q!.target, text: q!.text, typing: false };
  return (
    <Frame label="The latest question">
      <div className={styles.qa}>
        <span className={`meta ${styles.qaKicker}`}>
          Question {Math.min(status.questions + (asking ? 1 : 0), status.questions_total)} of {status.questions_total}
        </span>
        <Speaker seat={seat(shownQ.actor)} typing={shownQ.typing}>
          <span className={styles.who}>
            {nameOf(seats, shownQ.actor)}
            {shownQ.target ? <> asks <strong>{nameOf(seats, shownQ.target, "you")}</strong></> : " is asking…"}
          </span>
          <p className={styles.words} aria-live="polite">{shownQ.text || "…"}</p>
        </Speaker>
        {!asking && q && (
          <Speaker seat={seat(q.target)} typing={!!answering}>
            <span className={styles.who}>{nameOf(seats, q.target)}</span>
            <p className={styles.words} aria-live="polite">
              {a ? a.text : answering ? answering[1] || "…" : q.target === status.you ? "Your answer?" : "…"}
            </p>
          </Speaker>
        )}
      </div>
    </Frame>
  );
}

/** The vote (or the revote between the tied players): ballots appear one by one as they're revealed. */
export function SpyVoteStage({ status, seats, events, onVote, busy }: {
  status: SpyStatus;
  seats: SpySeat[];
  events: GameEvent[];
  onVote: (pid: string) => void;
  busy: boolean;
}) {
  const phase = status.phase === "revote" ? "revote" : "vote";
  const ballots: Record<string, string[]> = {};
  const first = [...events].reverse().find((e) => e.kind === "first"); // this round's votes only
  for (const e of events) {
    if (first && e.seq < first.seq) continue;
    if (e.kind === "vote" && e.phase === phase && e.target && e.actor) (ballots[e.target] ??= []).push(e.actor);
  }
  const counted = Object.values(ballots).flat().length;
  const myTurn = status.turn && (status.turn.type === "vote" || status.turn.type === "revote");
  const choices = new Set(myTurn && !busy ? status.turn!.targets : []);
  const living = seats.filter((s) => s.alive);
  const shown = phase === "revote" ? living.filter((s) => status.revote_between.includes(s.id) || s.you) : living;
  return (
    <PickTray
      title={myTurn ? (phase === "revote" ? "The vote tied. Who is it?" : "Who is the spy?") : "The votes are coming in."}
      kicker={`${status.survive_votes > 1 ? `Round ${status.round} · ` : ""}${phase === "revote" ? "Revote" : "Vote"}${counted ? ` · ${counted} in` : ""}`}
      seats={shown.map(asSeat)}
      choices={choices}
      onPick={myTurn ? onVote : undefined}
      ballots={ballots}
      footer={<span className="meta">{myTurn ? "Pick a portrait to lock your vote" : "Waiting for the others…"}</span>}
    />
  );
}

export function LastChanceStage({ status, seats }: { status: SpyStatus; seats: SpySeat[] }) {
  const spy = [...seats].find((s) => s.id === status.players.find((p) => p.role === "spy")?.id);
  const caught = status.role === "spy" ? "You were caught!" : `${spy ? spy.name : "The spy"} was caught!`;
  return (
    <AnnouncementStage kicker="Last chance" headline={caught}
                       detail={status.role === "spy" ? "Name the place: right and it's a draw." : "The spy gets one guess at the place."} />
  );
}
