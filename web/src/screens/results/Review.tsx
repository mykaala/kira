import { useState } from "react";
import { Button } from "../../components/Button";
import type { Seat } from "../../game/model";
import type { GameEvent, Status } from "../../types";
import { ChatLog } from "../game/ChatLog";
import { NotesPanel, useNotes } from "../game/Notes";
import styles from "./Review.module.css";

/** The whole game, start to finish; switch on Secrets to see every night action too. */
export function Review({ gameId, status, seats, events, reveal, onBack, log, side }: {
  gameId: string;
  status?: Status; // Mafia's role card; another game passes its own `side`
  seats: Seat[];
  events: GameEvent[];
  reveal: GameEvent[] | null;
  onBack: () => void;
  log?: React.ReactNode; // another game's log in place of the chat (Out of Place)
  side?: React.ReactNode; // and its side panel in place of the notes and role card
}) {
  const [secrets, setSecrets] = useState(false);
  const { notes, setNotes, pinned, pin } = useNotes(gameId);
  const shown = secrets && reveal ? reveal : events;
  return (
    <div className="lantern-page">
      <div className={styles.page}>
        <header className={styles.head}>
          <Button variant="surface" size="small" onClick={onBack} aria-label="Back to results">←</Button>
          <h1 className={styles.title}>The whole game</h1>
          {reveal && (
            <label className={styles.toggle}>
              <input type="checkbox" checked={secrets} onChange={(e) => setSecrets(e.target.checked)} />
              Show secrets
            </label>
          )}
        </header>
        <div className={styles.columns}>
          <div className={styles.chat}>
            {log ?? <ChatLog seats={seats} events={shown} pinned={pinned} onPin={pin} title="Every line" tall />}
          </div>
          {side ?? (status && <NotesPanel notes={notes} onNotes={setNotes} status={status} seats={seats} events={shown} />)}
        </div>
      </div>
    </div>
  );
}
