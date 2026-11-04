import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import type { Seat } from "../../game/model";
import type { GameEvent, Status } from "../../types";
import styles from "./Stage.module.css";

export function Frame({ night, compact, label, children }: {
  night?: boolean;
  compact?: boolean; // Mafia: a banner above the chat, not the whole stage
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-label={label} className={`${styles.stage} ${night ? styles.night : ""} ${compact ? styles.compact : ""}`}>
      <div className={styles.glow} aria-hidden="true" />
      {children}
    </section>
  );
}

/** Before anyone speaks: the morning's news, big. */
export function AnnouncementStage({ kicker, headline, detail, night, compact }: {
  kicker: string;
  headline: string;
  detail?: string;
  night?: boolean;
  compact?: boolean;
}) {
  return (
    <Frame night={night} compact={compact} label={kicker}>
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
export function PickTray({ title, kicker, seats, choices, onPick, chosen, ballots, footer, night, muted, compact }: {
  title: string;
  kicker: string;
  seats: Seat[];
  choices: Set<string>;
  onPick?: (pid: string) => void;
  chosen?: string | null;
  ballots?: Record<string, string[]>;
  footer?: React.ReactNode;
  night?: boolean;
  muted?: boolean;
  compact?: boolean;
}) {
  const voter = (pid: string) => seats.find((s) => s.id === pid);
  return (
    <Frame night={night} compact={compact} label={title}>
      <div className={styles.tray}>
        <div className={styles.trayHead}>
          <h2 className={styles.trayTitle}>{title}</h2>
          <span className={`meta ${styles.kicker}`}>{kicker}</span>
        </div>
        <div className={`${styles.picks} ${muted ? styles.muted : ""}`}>
          {seats.filter((s) => s.alive).map((s) => {
            const canPick = !!onPick && choices.has(s.id);
            const votes = ballots?.[s.id] ?? [];
            return (
              <button key={s.id} type="button" disabled={!canPick} onClick={() => onPick?.(s.id)}
                      className={`${styles.pick} ${chosen === s.id ? styles.chosen : ""}`}
                      aria-label={canPick ? `${title.split("?")[0]}: ${s.name}` : s.you ? "You" : s.name}>
                {s.character ? <Portrait character={s.character} size={compact ? 64 : 84} /> : <span className={styles.youSmall}>You</span>}
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
      <PickTray night compact title={action.title} kicker={`Night ${status.day} · ${action.verb}`} seats={seats}
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
  return <AnnouncementStage night compact kicker={`Night ${status.day}`} headline="The town sleeps." detail={detail} />;
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
      compact
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
