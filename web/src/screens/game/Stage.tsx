import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { moodOf, namedIn, replyingTo, type Seat, type StageLine } from "../../game/model";
import { reactionFor } from "../../game/reactions";
import type { GameEvent, Status } from "../../types";
import styles from "./Stage.module.css";

const MAX_REACTIONS = 3;

export function Frame({ night, label, children }: { night?: boolean; label: string; children: React.ReactNode }) {
  return (
    <section aria-label={label} className={`${styles.stage} ${night ? styles.night : ""}`}>
      <div className={styles.glow} aria-hidden="true" />
      {children}
    </section>
  );
}

/** One large speaker beside a cream speech bubble, with brief reactions from whoever they named. */
export function SpeechStage({ line, seats, events, day }: {
  line: StageLine;
  seats: Seat[];
  events: GameEvent[];
  day: number;
}) {
  const speaker = seats.find((s) => s.id === line.pid);
  if (!speaker) return null;
  const about = replyingTo(line, events, seats, day);
  const aboutSeat = seats.find((s) => s.id === about);
  const reactors = line.typing
    ? []
    : namedIn(line.text, seats, line.pid)
        .map((pid) => seats.find((s) => s.id === pid)!)
        .filter((s) => s.alive && s.character)
        .slice(0, MAX_REACTIONS);

  return (
    <Frame label="Now speaking">
      <div className={styles.speaker}>
        {speaker.character ? (
          <Portrait character={speaker.character} mood={moodOf(line)} size={220} shape="rounded"
                    className={styles.bigPortrait} label={`${speaker.name}${line.typing ? ", talking" : ""}`} />
        ) : (
          <div className={styles.youTile}>You</div>
        )}
        {/* no voice label here: during a game it would hint at how they think */}
        <span className={styles.nameTag}>{speaker.you ? "You" : speaker.name}</span>
      </div>
      <div className={styles.talk}>
        {aboutSeat && (
          <span className={styles.replying}>
            {aboutSeat.character ? <Portrait character={aboutSeat.character} size={24} /> : null}
            replying to {aboutSeat.you ? "you" : aboutSeat.name}
          </span>
        )}
        <div className={styles.bubble}>
          <svg className={styles.tail} width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
            <path d="M28 0 L0 14 L28 28 Z" fill="var(--text)" />
          </svg>
          <p className={styles.words} aria-live="polite">{line.text || " "}</p>
          {line.typing && (
            <div className={styles.dots} aria-label="still talking">
              <span /><span /><span />
            </div>
          )}
        </div>
        <div className={styles.reactions}>
          {reactors.map((s) => (
            <span key={`${line.seq}-${s.id}`} className={styles.reaction}>
              <strong style={{ color: `var(--c-${s.character})` }}>{s.name}</strong>{" "}
              {reactionFor(s.character!, (line.seq ?? 0) + s.id.length)}
            </span>
          ))}
        </div>
      </div>
    </Frame>
  );
}

/** Before anyone speaks: the morning's news, big. */
export function AnnouncementStage({ kicker, headline, detail, night }: {
  kicker: string;
  headline: string;
  detail?: string;
  night?: boolean;
}) {
  return (
    <Frame night={night} label={kicker}>
      <div className={styles.center}>
        <span className={`meta ${styles.kicker}`}>{kicker}</span>
        <h2 className={styles.headline}>{headline}</h2>
        {detail && <p className={styles.soft}>{detail}</p>}
      </div>
    </Frame>
  );
}

const NIGHT_VERB: Record<string, { verb: string; title: string }> = {
  mafia: { verb: "Kill", title: "Who doesn't wake up?" },
  doctor: { verb: "Protect", title: "Who do you watch over tonight?" },
  detective: { verb: "Investigate", title: "Whose secret do you check?" },
  bodyguard: { verb: "Guard", title: "Who do you stand in front of tonight?" },
};

/** A tray of portraits to pick from: the night action or the day vote. */
export function PickTray({ title, kicker, seats, choices, onPick, chosen, ballots, footer, night }: {
  title: string;
  kicker: string;
  seats: Seat[];
  choices: Set<string>;
  onPick?: (pid: string) => void;
  chosen?: string | null;
  ballots?: Record<string, string[]>;
  footer?: React.ReactNode;
  night?: boolean;
}) {
  const voter = (pid: string) => seats.find((s) => s.id === pid);
  return (
    <Frame night={night} label={title}>
      <div className={styles.tray}>
        <div className={styles.trayHead}>
          <h2 className={styles.trayTitle}>{title}</h2>
          <span className={`meta ${styles.kicker}`}>{kicker}</span>
        </div>
        <div className={styles.picks}>
          {seats.filter((s) => s.alive).map((s) => {
            const canPick = !!onPick && choices.has(s.id);
            const votes = ballots?.[s.id] ?? [];
            return (
              <button key={s.id} type="button" disabled={!canPick} onClick={() => onPick?.(s.id)}
                      className={`${styles.pick} ${chosen === s.id ? styles.chosen : ""}`}
                      aria-label={canPick ? `${title.split("?")[0]}: ${s.name}` : s.you ? "You" : s.name}>
                {s.character ? <Portrait character={s.character} size={84} /> : <span className={styles.youSmall}>You</span>}
                <span className={styles.pickName}>{s.you ? "You" : s.name}</span>
                {ballots && (
                  <span className={styles.ballots}>
                    {votes.map((v, i) => {
                      const who = voter(v);
                      return who?.character ? (
                        <Portrait key={`${v}-${i}`} character={who.character} size={22} className={styles.ballot} />
                      ) : (
                        <span key={`${v}-${i}`} className={`${styles.ballot} ${styles.count}`}>you</span>
                      );
                    })}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {footer && <div className={styles.trayFoot}>{footer}</div>}
      </div>
    </Frame>
  );
}

export function NightStage({ status, seats, onPick, onSkip, picked }: {
  status: Status;
  seats: Seat[];
  onPick: (pid: string) => void;
  onSkip: () => void;
  picked: string | null;
}) {
  const action = NIGHT_VERB[status.role];
  const me = seats.find((s) => s.you);
  if (me?.alive && action && status.waiting_on_you && status.legal_actions.length && !picked) {
    const choices = new Set(status.legal_actions.filter((a) => a !== "abstain"));
    return (
      <PickTray night title={action.title} kicker={`Night ${status.day} · ${action.verb}`} seats={seats}
                choices={choices} onPick={onPick}
                footer={status.legal_actions.includes("abstain") && (
                  <Button variant="ghost" size="small" onClick={onSkip}>Skip tonight</Button>
                )} />
    );
  }
  const detail = !me?.alive
    ? "You're out, but you can still watch."
    : picked
      ? "Your choice is in. The night goes on without you."
      : status.role === "villager" || status.role === "jester"
        ? "Close your eyes. Someone is moving in the dark."
        : "Nothing for you to do tonight. Rest.";
  return <AnnouncementStage night kicker={`Night ${status.day}`} headline="The town sleeps." detail={detail} />;
}

export function VoteTray({ status, seats, events, onVote, voted }: {
  status: Status;
  seats: Seat[];
  events: GameEvent[];
  onVote: (pid: string | "abstain") => void;
  voted: string | null;
}) {
  const today = events.filter((e) => e.day === status.day && (e.kind === "vote" || e.kind === "elimination"));
  const ballots: Record<string, string[]> = {};
  let abstains = 0;
  for (const e of today) {
    if (e.kind !== "vote" || !e.actor) continue;
    if (e.target) (ballots[e.target] ??= []).push(e.actor);
    else abstains += 1;
  }
  const verdict = today.find((e) => e.kind === "elimination");
  const canVote = status.waiting_on_you && status.legal_actions.length > 0 && !voted;
  const choices = new Set(canVote ? status.legal_actions.filter((a) => a !== "abstain") : []);
  const counted = today.filter((e) => e.kind === "vote").length;

  return (
    <PickTray
      title={verdict ? "The town has spoken." : canVote ? "Who goes?" : "The votes are coming in."}
      kicker={`Day ${status.day} · Vote${counted ? ` · ${counted} in` : ""}`}
      seats={seats}
      choices={choices}
      onPick={canVote ? onVote : undefined}
      chosen={voted}
      ballots={ballots}
      footer={
        <>
          {verdict ? <p className={styles.verdict}>{verdict.text}</p> : (
            <span className="meta">{abstains ? `${abstains} abstained` : canVote ? "Pick a portrait to lock your vote" : ""}</span>
          )}
          {canVote && status.legal_actions.includes("abstain") && (
            <Button variant="ghost" size="small" onClick={() => onVote("abstain")}>Abstain</Button>
          )}
        </>
      }
    />
  );
}
