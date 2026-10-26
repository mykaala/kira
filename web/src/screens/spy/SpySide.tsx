import { usePersisted } from "../../persisted";
import type { SpyStatus } from "../../spy/types";
import noteStyles from "../game/Notes.module.css";
import styles from "./SpyGame.module.css";

/** Your secret first (the place, or "You're the spy" with the places list), then always-open notes. */
export function SpySide({ gameId, status, places, onPickPlace, canGuess }: {
  gameId: string;
  status: SpyStatus;
  places: string[];
  onPickPlace: (p: string) => void;
  canGuess: boolean; // your turn to name the place
}) {
  const [notes, setNotes] = usePersisted(`kira:${gameId}:notes`, "");
  const [showPlaces, setShowPlaces] = usePersisted("kira:spy-places-list", true);
  return (
    <aside className={noteStyles.panel} aria-label="Your notes and your secret">
      <div className={`${noteStyles.secret} ${styles.secretFirst}`}>
        <span className={`meta ${noteStyles.secretLabel}`}>Your secret</span>
        {"place" in status.secret ? (
          <>
          <p className={noteStyles.secretText}>
            You're a <strong style={{ color: "var(--teal)" }}>civilian</strong>. The place is{" "}
            <strong className={styles.place}>{status.secret.place}</strong>. Don't say it: the spy is listening.
          </p>
          {status.secret.role && (
            <div className={styles.roleCard} aria-label="Your role at the place">
              <p className={noteStyles.secretText}>
                Your role here: <strong>{status.secret.role.title}</strong>. Keep it secret too.
              </p>
              <dl className={styles.roleFacts}>
                <dt>You wear</dt><dd>{status.secret.role.wears}</dd>
                <dt>You</dt><dd>{status.secret.role.does}</dd>
                <dt>You deal with</dt><dd>{status.secret.role.deals_with}</dd>
              </dl>
            </div>
          )}
          </>
        ) : (
          <>
            <p className={noteStyles.secretText}>
              <strong style={{ color: "var(--coral)" }}>You're the spy.</strong> You don't know the place. Blend in,
              and name it on your turn if you can tell.
            </p>
            <label className={styles.placesToggle}>
              <input type="checkbox" checked={showPlaces} onChange={(e) => setShowPlaces(e.target.checked)} />
              Show the places list <span className={styles.muted}>(the AI spy doesn't get one)</span>
            </label>
            {showPlaces && (
              <ul className={styles.places} aria-label="Places it could be">
                {places.map((p) => (
                  <li key={p}>
                    <button type="button" className={styles.placeBtn} disabled={!canGuess} onClick={() => onPickPlace(p)}
                            title={canGuess ? "Put this in your guess" : "You can name the place on your turn to ask"}>
                      {p}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
      <label htmlFor="notes" className={noteStyles.title}>Notes</label>
      <textarea id="notes" className={noteStyles.notes} value={notes} spellCheck={false}
                placeholder={"who sounded unsure, who was too vague…"} onChange={(e) => setNotes(e.target.value)} />
    </aside>
  );
}
