import { useState } from "react";
import { Button } from "../../components/Button";
import { MAX_AI, MIN_AI, mafiaCount, type LobbySettings } from "../../game/lobby";
import { DIFFICULTIES, type Difficulty } from "../../game/tuning";
import { LobbyFrame, SeatTable, Stepper, SwitchPills, addSeat, dropSeat } from "./LobbyParts";
import styles from "./Lobby.module.css";

type Extra = "jester" | "bodyguard";
const EXTRA_HINT: Record<Extra, string> = {
  jester: "Jester wins alone if voted out.",
  bodyguard: "Bodyguard dies in place of whoever they guard.",
};

/** Set the Mafia table: swap seats at the table; name, seats, how sharp and roles in one card beside it. */
export function Lobby({ settings, difficulty, onChange, onStart }: {
  settings: LobbySettings;
  difficulty: Difficulty;
  onChange: (s: LobbySettings) => void;
  onStart: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const s = settings;
  const set = (patch: Partial<LobbySettings>) => onChange({ ...s, ...patch });
  const n = s.cast.length;

  const start = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onStart();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <LobbyFrame game="Mafia" title="Who’s at the table tonight?" sub="Tap a seat to swap who sits there." onSubmit={start}
                table={<SeatTable seats={s.cast} onSeats={(cast) => set({ cast })} minSeats={MIN_AI}
                                  count={mafiaCount(n + 1)} hiding="Mafia hiding" />}>
      <section className={`${styles.panel} ${styles.raised}`} aria-label="House rules">
        <h2 className={styles.h2}>House rules</h2>
        <label className={styles.field}>
          <span className={`meta ${styles.label}`}>What do they call you?</span>
          <input className={styles.input} value={s.name} maxLength={20} placeholder="Your name" required
                 onChange={(e) => set({ name: e.target.value })} />
        </label>
        <div className={styles.row}>
          <Stepper label="AI players" value={n} min={MIN_AI} max={MAX_AI}
                   onChange={(v) => set({ cast: v > n ? addSeat(s.cast) : dropSeat(s.cast) })} />
          <div className={styles.field}>
            <span className={`meta ${styles.label}`}>How sharp</span>
            <a href="#/characters" className={styles.sharp} aria-label="How sharp they play: tune on the Characters page">
              {DIFFICULTIES.find((d) => d.id === difficulty)?.label} · tune ↗
            </a>
          </div>
        </div>
        <SwitchPills
          label="Roles"
          idle="Doctor and Detective are always in. Extras replace a villager."
          pills={[
            { id: "doctor", name: "Doctor", tone: "var(--teal)", on: true, fixed: true },
            { id: "detective", name: "Detective", tone: "var(--lavender)", on: true, fixed: true },
            { id: "jester", name: "Jester", tone: "var(--lantern)", on: s.roles.jester, hint: EXTRA_HINT.jester },
            { id: "bodyguard", name: "Bodyguard", tone: "var(--coral)", on: s.roles.bodyguard, hint: EXTRA_HINT.bodyguard },
          ]}
          onToggle={(id) => set({ roles: { ...s.roles, [id]: !s.roles[id as Extra] } })}
        />
      </section>

      {error && <p className={styles.error} role="alert">{error}</p>}
      <Button variant="lantern" size="large" type="submit" block disabled={busy || !s.name.trim()}>
        {busy ? "Dealing roles…" : "Blow out the lantern →"}
      </Button>
    </LobbyFrame>
  );
}
