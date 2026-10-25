/** Lobby settings: Auto (a random table) by default; choosing the cast, knobs and roles is advanced. */
import { CHARACTER_IDS, type CharacterId, type Traits } from "../cast";

export type Difficulty = "cozy" | "tricky" | "merciless";
export type Shift = { suspicious: number; liar: number };

export type LobbySettings = {
  name: string;
  opponents: number; // AI seats when the cast is random
  chooseCast: boolean;
  cast: CharacterId[]; // AI seats when chosen
  traits: Partial<Record<CharacterId, Traits>>; // knobs you've set by hand
  difficulty: Difficulty;
  roles: { jester: boolean; bodyguard: boolean };
};

export const DEFAULT_LOBBY: LobbySettings = {
  name: "",
  opponents: 6,
  chooseCast: false,
  cast: ["ines", "bram", "odile", "tobiah", "kit", "marguerite"],
  traits: {},
  difficulty: "tricky",
  roles: { jester: false, bodyguard: false },
};

export const MIN_AI = 4;
export const MAX_AI = 8;

export const aiSeats = (s: LobbySettings) => (s.chooseCast ? s.cast.length : s.opponents);
/** Mafia hiding at a table of n players, matching the engine (1 up to 6 players, then 2). */
export const mafiaCount = (players: number) => (players <= 6 ? 1 : 2);

const clamp = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 100) / 100;

/** A character's knobs as they'll play: set by hand, or their base shifted by the difficulty. */
export function effectiveTraits(base: Traits, s: LobbySettings, id: CharacterId, shifts: Record<string, Shift>): Traits {
  const own = s.traits[id];
  if (own) return own;
  const d = shifts[s.difficulty] ?? { suspicious: 0, liar: 0 };
  return { talkative: base.talkative, suspicious: clamp(base.suspicious + d.suspicious), liar: clamp(base.liar + d.liar) };
}

export const benchOf = (s: LobbySettings) => CHARACTER_IDS.filter((id) => !s.cast.includes(id));

/** The new-game request. Anything you didn't choose is left for the server to deal at random. */
export function newGameRequest(s: LobbySettings, auto: boolean) {
  const roles = (Object.keys(s.roles) as (keyof LobbySettings["roles"])[]).filter((r) => s.roles[r]);
  const base = { name: s.name.trim(), auto, difficulty: s.difficulty, roles };
  if (!s.chooseCast) return { ...base, opponents: s.opponents };
  const traits = Object.fromEntries(Object.entries(s.traits).filter(([id]) => s.cast.includes(id as CharacterId)));
  return { ...base, cast: s.cast, ...(Object.keys(traits).length ? { traits } : {}) };
}
