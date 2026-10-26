import { useState } from "react";
import { Button } from "../../components/Button";
import { MAX_PLAYERS, MIN_PLAYERS, type SpyLobbySettings, type SpyRolePick } from "../../spy/lobby";
import { LobbyFrame, SeatTable, Stepper, SwitchPills, addSeat, dropSeat } from "../lobby/LobbyParts";
import styles from "../lobby/Lobby.module.css";

const ROLES: { id: SpyRolePick; label: string }[] = [
  { id: "random", label: "Random" },
  { id: "civilian", label: "Civilian" },
  { id: "spy", label: "Spy" },
];

/** Set the table for Out of Place: swap seats at the table; name, players, your role and the extras beside it. */
export function SpyLobby({ title, settings, onChange, onStart }: {
  title: string;
  settings: SpyLobbySettings;
  onChange: (s: SpyLobbySettings) => void;
  onStart: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const s = settings;
  const set = (patch: Partial<SpyLobbySettings>) => onChange({ ...s, ...patch });
  const seat = (cast: SpyLobbySettings["cast"]) => set({ cast, players: cast.length + 1 });

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
    <LobbyFrame game={title} title="Everyone knows where you are. Almost." onSubmit={start}
                sub="One spy doesn’t know the place. Tap a seat to swap who sits there."
                table={<SeatTable seats={s.cast} onSeats={seat} minSeats={MIN_PLAYERS - 1} count={1} hiding="spy hiding" />}>
      <section className={`${styles.panel} ${styles.raised}`} aria-label="House rules">
        <h2 className={styles.h2}>House rules</h2>
        <label className={styles.field}>
          <span className={`meta ${styles.label}`}>What do they call you?</span>
          <input className={styles.input} value={s.name} maxLength={20} placeholder="Your name" required
                 autoComplete="nickname" onChange={(e) => set({ name: e.target.value })} />
        </label>
        <Stepper label="Players, you included" value={s.players} min={MIN_PLAYERS} max={MAX_PLAYERS}
                 onChange={(v) => seat(v > s.players ? addSeat(s.cast) : dropSeat(s.cast))} />
        <div className={styles.field}>
          <span className={`meta ${styles.label}`} id="spy-role">Your role</span>
          <div className={styles.seg} role="group" aria-labelledby="spy-role">
            {ROLES.map((r) => (
              <button key={r.id} type="button" className={styles.segBtn} aria-pressed={s.role === r.id}
                      onClick={() => set({ role: r.id })}>
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <SwitchPills
          label="Extras"
          idle="A plain round: no roles, free questions."
          pills={[
            { id: "roles", name: "Place roles", tone: "var(--teal)", on: s.roles, hint: "Each civilian gets a secret role at the place." },
            { id: "angles", name: "Angles", tone: "var(--lavender)", on: s.askAngle, hint: "AI questions follow a set topic." },
          ]}
          onToggle={(id) => set(id === "roles" ? { roles: !s.roles } : { askAngle: !s.askAngle })}
        />
      </section>

      {error && <p className={styles.error} role="alert">{error}</p>}
      <Button variant="lantern" size="large" type="submit" block disabled={busy || !s.name.trim()}>
        {busy ? "Picking the place…" : "Pick the place →"}
      </Button>
    </LobbyFrame>
  );
}
