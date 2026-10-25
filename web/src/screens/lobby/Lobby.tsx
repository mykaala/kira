import { useEffect, useState } from "react";
import { Button } from "../../components/Button";
import { Portrait } from "../../components/Portrait";
import { TraitBar } from "../../components/TraitBar";
import type { CharacterId, Traits } from "../../cast";
import {
  MAX_AI, MIN_AI, aiSeats, benchOf, effectiveTraits, mafiaCount,
  type Difficulty, type LobbySettings, type Shift,
} from "../../game/lobby";
import { useCast } from "../../useCast";
import { RoundTable } from "./RoundTable";
import styles from "./Lobby.module.css";

const DIFFICULTIES: { id: Difficulty; label: string }[] = [
  { id: "cozy", label: "Cozy" },
  { id: "tricky", label: "Tricky" },
  { id: "merciless", label: "Merciless" },
];
const MAX_PLAYERS = 9;

/** Set the table: house rules up front; who sits down and their knobs under Advanced settings. */
export function Lobby({ settings, onChange, onStart }: {
  settings: LobbySettings;
  onChange: (s: LobbySettings) => void;
  onStart: () => Promise<void>;
}) {
  const cast = useCast();
  const [shifts, setShifts] = useState<Record<string, Shift>>({});
  const [selected, setSelected] = useState<CharacterId | null>(null);
  const [advanced, setAdvanced] = useState(settings.chooseCast);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/difficulty").then((r) => r.json()).then(setShifts).catch(() => undefined);
  }, []);

  const s = settings;
  const set = (patch: Partial<LobbySettings>) => onChange({ ...s, ...patch });
  const n = aiSeats(s);
  const customKnobs = Object.keys(s.traits).some((id) => s.cast.includes(id as CharacterId)) && s.chooseCast;
  const bench = benchOf(s);
  const sel = selected && s.chooseCast && s.cast.includes(selected) ? selected : null;

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

  const traitsOf = (id: CharacterId): Traits =>
    cast[id] ? effectiveTraits(cast[id]!.traits, s, id, shifts) : { talkative: 0.5, suspicious: 0.5, liar: 0.5 };
  const setTrait = (id: CharacterId, key: keyof Traits, v: number) =>
    set({ traits: { ...s.traits, [id]: { ...traitsOf(id), [key]: v } } });
  const resetKnobs = (id: CharacterId) => {
    const { [id]: _, ...rest } = s.traits;
    set({ traits: rest });
  };
  const swap = (id: CharacterId) => {
    const next = bench[0];
    if (!next) return;
    set({ cast: s.cast.map((c) => (c === id ? next : c)) });
    setSelected(next);
  };
  const empty = (id: CharacterId) => {
    set({ cast: s.cast.filter((c) => c !== id) });
    setSelected(null);
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
            <span className={`meta ${styles.path}`}>/ Mafia / Set the table</span>
          </div>
          <span className={`meta ${styles.filled}`}>{n + 1} of {MAX_PLAYERS} seats filled</span>
        </header>

        <div className={styles.columns}>
          <section className={styles.left}>
            <h1 className={styles.title}>Who’s at the table tonight?</h1>
            <p className={styles.sub}>
              {s.chooseCast
                ? "Tap a seat to see them up close, swap them out, or turn their knobs. Roles are dealt when the lantern goes dark."
                : "A random table. Open Advanced settings to choose who sits down. Roles are dealt when the lantern goes dark."}
            </p>
            <RoundTable
              seats={s.chooseCast ? s.cast : Array.from({ length: n }, () => null)}
              mafia={mafiaCount(n + 1)}
              cast={cast}
              selected={sel}
              onSelect={(id) => {
                if (!s.chooseCast) setAdvanced(true);
                setSelected(id);
              }}
            />
          </section>

          <div className={styles.right}>
            <section className={`${styles.panel} ${styles.raised}`} aria-label="House rules">
              <h2 className={styles.h2}>House rules</h2>
              <label className={styles.field}>
                <span className={`meta ${styles.label}`}>What do they call you?</span>
                <input className={styles.input} value={s.name} maxLength={20} placeholder="Your name" required
                       onChange={(e) => set({ name: e.target.value })} />
              </label>
              {!s.chooseCast && (
                <div className={styles.field}>
                  <span className={`meta ${styles.label}`} id="ai-count">AI players</span>
                  <div className={styles.stepper} role="group" aria-labelledby="ai-count">
                    <button type="button" className={styles.step} aria-label="One fewer"
                            disabled={s.opponents <= MIN_AI} onClick={() => set({ opponents: s.opponents - 1 })}>−</button>
                    <span className={styles.stepValue} aria-live="polite">{s.opponents}</span>
                    <button type="button" className={styles.step} aria-label="One more"
                            disabled={s.opponents >= MAX_AI} onClick={() => set({ opponents: s.opponents + 1 })}>+</button>
                  </div>
                </div>
              )}
              <div className={styles.field}>
                <span className={`meta ${styles.label}`}>Roles</span>
                <div className={styles.roles}>
                  <button type="button" className={styles.role} aria-pressed="true" disabled>✓ Doctor</button>
                  <button type="button" className={styles.role} aria-pressed="true" disabled>✓ Detective</button>
                  {(["jester", "bodyguard"] as const).map((r) => (
                    <button key={r} type="button" className={styles.role} aria-pressed={s.roles[r]}
                            onClick={() => set({ roles: { ...s.roles, [r]: !s.roles[r] } })}>
                      {s.roles[r] ? "✓" : "+"} {r[0].toUpperCase() + r.slice(1)}
                    </button>
                  ))}
                </div>
                <p className={styles.roleHint}>
                  {s.roles.jester && "Jester wins alone if voted out. "}
                  {s.roles.bodyguard && "Bodyguard dies in place of whoever they guard. "}
                  {!s.roles.jester && !s.roles.bodyguard && "Doctor and Detective are always in. Extras replace a villager."}
                </p>
              </div>
              <div className={styles.field}>
                <span className={`meta ${styles.label}`} id="sharp">
                  How sharp are they?{customKnobs && <span className={styles.custom}> · custom knobs</span>}
                </span>
                <div className={styles.seg} role="group" aria-labelledby="sharp">
                  {DIFFICULTIES.map((d) => (
                    <button key={d.id} type="button" className={styles.segBtn}
                            aria-pressed={s.difficulty === d.id && !customKnobs}
                            onClick={() => set({ difficulty: d.id, traits: {} })}>
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <details className={styles.details} open={advanced}
                     onToggle={(e) => setAdvanced((e.target as HTMLDetailsElement).open)}>
              <summary className={styles.summary}>
                <span className={styles.summaryTitle}>Advanced settings</span>
                <span className={styles.summaryNote}>{s.chooseCast ? "Cast chosen" : "Auto · random"} <span className={styles.chev}>▾</span></span>
              </summary>
              <div className={styles.detailsBody}>
                <label className={styles.switchRow}>
                  <span>Choose who sits down</span>
                  <input type="checkbox" checked={s.chooseCast} onChange={(e) => set({ chooseCast: e.target.checked })} />
                </label>
                {s.chooseCast ? (
                  <>
                    <div className={styles.field}>
                      <span className={`meta ${styles.label}`}>On the bench</span>
                      <div className={styles.bench}>
                        {bench.length === 0 && <span className={styles.hint}>Everyone is seated.</span>}
                        {bench.map((id) => (
                          <button key={id} type="button" className={styles.benchBtn} disabled={s.cast.length >= MAX_AI}
                                  onClick={() => {
                                    set({ cast: [...s.cast, id] });
                                    setSelected(id);
                                  }}>
                            <Portrait character={id} size={36} />+ {cast[id]?.name ?? id}
                          </button>
                        ))}
                      </div>
                    </div>
                    {sel ? (
                      <UpClose
                        id={sel}
                        seat={s.cast.indexOf(sel) + 1}
                        character={cast[sel]}
                        traits={traitsOf(sel)}
                        custom={!!s.traits[sel]}
                        swapFor={bench[0] ? cast[bench[0]]?.name ?? bench[0] : null}
                        canEmpty={s.cast.length > MIN_AI}
                        onTrait={(k, v) => setTrait(sel, k, v)}
                        onReset={() => resetKnobs(sel)}
                        onSwap={() => swap(sel)}
                        onEmpty={() => empty(sel)}
                      />
                    ) : (
                      <p className={styles.hint}>Tap a seat on the table to see them up close and turn their knobs.</p>
                    )}
                  </>
                ) : (
                  <p className={styles.hint}>
                    Auto deals {s.opponents} random characters with their usual temperament, shifted by how sharp you
                    picked. Switch this on to choose the cast and set each one's knobs.
                  </p>
                )}
              </div>
            </details>

            {error && <p className={styles.error} role="alert">{error}</p>}
            <Button variant="lantern" size="large" type="submit" block disabled={busy || !s.name.trim()}>
              {busy ? "Dealing roles…" : "Blow out the lantern →"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}

function UpClose({ id, seat, character, traits, custom, swapFor, canEmpty, onTrait, onReset, onSwap, onEmpty }: {
  id: CharacterId;
  seat: number;
  character?: { full_name: string; voice: string; quote: string };
  traits: Traits;
  custom: boolean;
  swapFor: string | null;
  canEmpty: boolean;
  onTrait: (k: keyof Traits, v: number) => void;
  onReset: () => void;
  onSwap: () => void;
  onEmpty: () => void;
}) {
  return (
    <section className={styles.upClose} aria-label="Up close">
      <div className={styles.upHead}>
        <span className={styles.h2}>Up close</span>
        <span className={`meta ${styles.label}`}>Seat {seat} · selected</span>
      </div>
      <div className={styles.who}>
        <Portrait character={id} mood="smug" size={88} shape="rounded" />
        <div className={styles.whoText}>
          <span className={styles.fullName}>{character?.full_name ?? id}</span>
          <span className={styles.voice}>{character?.voice}</span>
          <span className={styles.quote}>“{character?.quote}”</span>
        </div>
      </div>
      <TraitBar label="Talkative" value={traits.talkative} onChange={(v) => onTrait("talkative", v)} />
      <TraitBar label="Suspicious" value={traits.suspicious} onChange={(v) => onTrait("suspicious", v)} />
      <TraitBar label="Good liar" value={traits.liar} onChange={(v) => onTrait("liar", v)} />
      {custom && <Button variant="ghost" size="small" onClick={onReset}>Reset knobs</Button>}
      <div className={styles.actions}>
        <Button variant="ghost" size="small" disabled={!swapFor} onClick={onSwap}>
          {swapFor ? `Swap for ${swapFor}` : "No one to swap in"}
        </Button>
        <Button variant="ghost" size="small" disabled={!canEmpty} onClick={onEmpty}>Empty seat</Button>
      </div>
    </section>
  );
}
