/** How sharp the AIs play, set on the Characters page: a difficulty for everyone, and knobs set by hand per
 * character, which win over it. Mafia sends every seat's knobs explicitly, so what the page shows is what plays. */
import { useEffect, useState } from "react";
import type { CharacterId, Traits } from "../cast";
import { getCast } from "../useCast";

export type Difficulty = "cozy" | "tricky" | "merciless";
export type Shift = { suspicious: number; liar: number };
export type Shifts = Partial<Record<Difficulty, Shift>>;

export type Tuning = {
  difficulty: Difficulty;
  traits: Partial<Record<CharacterId, Traits>>; // knobs set by hand
};

export const DEFAULT_TUNING: Tuning = { difficulty: "tricky", traits: {} };

export const DIFFICULTIES: { id: Difficulty; label: string; blurb: string }[] = [
  { id: "cozy", label: "Cozy", blurb: "Slow to accuse, easy to read." },
  { id: "tricky", label: "Tricky", blurb: "Everyone as they really are." },
  { id: "merciless", label: "Merciless", blurb: "Every archetype at its sharpest." },
];

let cached: Promise<Shifts> | null = null;

/** How each difficulty shifts suspicious and good liar (the server's numbers, so the strategy line matches). */
export function getShifts(): Promise<Shifts> {
  cached ??= fetch("/api/difficulty")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`difficulty ${r.status}`))))
    .catch((e) => {
      cached = null;
      throw e;
    });
  return cached;
}

export function useShifts(): Shifts {
  const [shifts, setShifts] = useState<Shifts>({});
  useEffect(() => {
    getShifts().then(setShifts).catch(() => undefined);
  }, []);
  return shifts;
}

const round = (v: number, lo = 0, hi = 1) => Math.round(Math.min(hi, Math.max(lo, v)) * 100) / 100;
/** Merciless pushes each knob away from the middle, so every archetype plays as its sharpest self. */
const SHARPEN = 1.5;
const sharpen = (v: number) => 0.5 + (v - 0.5) * SHARPEN;

/** A character's knobs as they'll play: set by hand, or their base under the difficulty. */
export function effectiveTraits(base: Traits, tuning: Tuning, id: CharacterId, shifts: Shifts): Traits {
  const own = tuning.traits[id];
  if (own) return own;
  const d = shifts[tuning.difficulty] ?? { suspicious: 0, liar: 0 };
  if (tuning.difficulty === "merciless") {
    // never all the way to 0 or 1: the most of their archetype, not a caricature
    const edge = (v: number) => round(v, 0.05, 0.95);
    return {
      talkative: edge(sharpen(base.talkative)),
      suspicious: edge(sharpen(base.suspicious) + d.suspicious),
      liar: edge(sharpen(base.liar) + d.liar),
    };
  }
  return { talkative: base.talkative, suspicious: round(base.suspicious + d.suspicious), liar: round(base.liar + d.liar) };
}

/** Every seat's knobs for a new game. */
export async function seatTraits(seats: CharacterId[], tuning: Tuning): Promise<Partial<Record<CharacterId, Traits>>> {
  const [cast, shifts] = await Promise.all([getCast(), getShifts()]);
  return Object.fromEntries(
    seats.filter((id) => cast[id]).map((id) => [id, effectiveTraits(cast[id]!.traits, tuning, id, shifts)]),
  );
}
