import { useState } from "react";
import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { CHARACTER_IDS, type CharacterId } from "../../cast";
import { MAX_PLAYERS, MIN_PLAYERS, type SpyLobbySettings, type SpyRolePick } from "../../spy/lobby";
import { useCast } from "../../useCast";
import { RoundTable } from "../lobby/RoundTable";
import styles from "../lobby/Lobby.module.css";
import own from "./SpyGame.module.css";

const ROLES: { id: SpyRolePick; label: string }[] = [
  { id: "random", label: "Random" },
  { id: "civilian", label: "Civilian" },
  { id: "spy", label: "Spy" },
];

/** Set the table for Out of Place: your name, how many sit down, your role, and (optionally) who plays. */
export function SpyLobby({ title, settings, onChange, onStart }: {
  title: string;
  settings: SpyLobbySettings;
  onChange: (s: SpyLobbySettings) => void;
  onStart: () => Promise<void>;
}) {
  const cast = useCast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const s = settings;
  const set = (patch: Partial<SpyLobbySettings>) => onChange({ ...s, ...patch });
  const ai = s.players - 1;
  const chosen = s.cast.slice(0, ai);
  const castReady = !s.chooseCast || chosen.length === ai;

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
  const toggle = (id: CharacterId) => {
    if (chosen.includes(id)) set({ cast: chosen.filter((c) => c !== id) });
    else if (chosen.length < ai) set({ cast: [...chosen, id] });
  };

  return (
    <div className="lantern-page">
      <form className={styles.page} onSubmit={start}>
        <header className={styles.header}>
          <div className={styles.crumbs}>
            <a href="#/" className={styles.back} aria-label="Back to games">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true">
                <path d="M19 12H5M11 6l-6 6 6 6" />
              </svg>
            </a>
            <span className={styles.word}>Kira</span>
            <span className={`meta ${styles.path}`}>/ {title} / Set the table</span>
          </div>
          <span className={`meta ${styles.filled}`}>{s.players} players · one spy</span>
        </header>

        <div className={styles.columns}>
          <section className={styles.left}>
            <h1 className={styles.title}>Everyone knows where you are. Almost.</h1>
            <p className={styles.sub}>
              One player is a spy who doesn't know the place. Take turns asking each other one question each, then
              vote. The spy can name the place on their turn, or once caught.
            </p>
            <RoundTable seats={s.chooseCast ? chosen : Array.from({ length: ai }, () => null)} mafia={1} cast={cast}
                        selected={null} onSelect={() => set({ chooseCast: true })} hiding="spy hiding" />
          </section>

          <div className={styles.right}>
            <section className={`${styles.panel} ${styles.raised}`} aria-label="House rules">
              <h2 className={styles.h2}>House rules</h2>
              <label className={styles.field}>
                <span className={`meta ${styles.label}`}>What do they call you?</span>
                <input className={styles.input} value={s.name} maxLength={20} placeholder="Your name" required
                       autoComplete="nickname" onChange={(e) => set({ name: e.target.value })} />
              </label>
              <div className={styles.field}>
                <span className={`meta ${styles.label}`} id="spy-players">Players, you included</span>
                <div className={styles.stepper} role="group" aria-labelledby="spy-players">
                  <button type="button" className={styles.step} aria-label="One fewer"
                          disabled={s.players <= MIN_PLAYERS} onClick={() => set({ players: s.players - 1 })}>−</button>
                  <span className={styles.stepValue} aria-live="polite">{s.players}</span>
                  <button type="button" className={styles.step} aria-label="One more"
                          disabled={s.players >= MAX_PLAYERS} onClick={() => set({ players: s.players + 1 })}>+</button>
                </div>
              </div>
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
            </section>

            <details className={styles.details} open={s.chooseCast}>
              <summary className={styles.summary}>
                <span className={styles.summaryTitle}>Who plays</span>
                <span className={styles.summaryNote}>{s.chooseCast ? `${chosen.length} of ${ai} chosen` : "Random table"} <span className={styles.chev}>▾</span></span>
              </summary>
              <div className={styles.detailsBody}>
                <label className={styles.switchRow}>
                  <span>Choose who sits down</span>
                  <input type="checkbox" checked={s.chooseCast} onChange={(e) => set({ chooseCast: e.target.checked })} />
                </label>
                {s.chooseCast ? (
                  <div className={styles.bench} role="group" aria-label={`Pick ${ai} characters`}>
                    {CHARACTER_IDS.map((id) => {
                      const on = chosen.includes(id);
                      return (
                        <button key={id} type="button" className={styles.benchBtn} aria-pressed={on}
                                disabled={!on && chosen.length >= ai} onClick={() => toggle(id)}
                                style={on ? { borderColor: "var(--lantern)" } : undefined}>
                          <Portrait character={id} size={36} />
                          {on ? "✓" : "+"} {cast[id]?.name ?? id}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <p className={styles.hint}>{ai} random characters sit down with you.</p>
                )}
                {s.chooseCast && !castReady && <p className={styles.hint}>Pick {ai - chosen.length} more.</p>}
              </div>
            </details>

            <details className={styles.details}>
              <summary className={styles.summary}>
                <span className={styles.summaryTitle}>Advanced</span>
                <span className={styles.summaryNote}>
                  {[s.roles ? "Roles on" : "Roles off", s.askAngle ? "angles on" : null].filter(Boolean).join(", ")}{" "}
                  <span className={styles.chev}>▾</span>
                </span>
              </summary>
              <div className={styles.detailsBody}>
                <div className={own.option}>
                  <label className={styles.switchRow}>
                    <span>Roles at the place</span>
                    <input type="checkbox" checked={s.roles} aria-describedby="spy-roles-hint"
                           onChange={(e) => set({ roles: e.target.checked })} />
                  </label>
                  <p id="spy-roles-hint" className={`${styles.hint} ${own.optionHint}`}>
                    Every civilian also gets a secret role there, like a regular or someone who works there. The spy gets none.
                  </p>
                </div>
                <div className={own.option}>
                  <label className={styles.switchRow}>
                    <span>Question angles</span>
                    <input type="checkbox" checked={s.askAngle} aria-describedby="spy-angle-hint"
                           onChange={(e) => set({ askAngle: e.target.checked })} />
                  </label>
                  <p id="spy-angle-hint" className={`${styles.hint} ${own.optionHint}`}>
                    The AI players ask about a set topic each turn: clothes, tools, who they deal with, or a typical problem.
                  </p>
                </div>
              </div>
            </details>

            {error && <p className={styles.error} role="alert">{error}</p>}
            <Button variant="lantern" size="large" type="submit" block disabled={busy || !s.name.trim() || !castReady}>
              {busy ? "Picking the place…" : "Pick the place →"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
