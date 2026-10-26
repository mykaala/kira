/** Lobby settings. The table is always a real cast you can see: dealt at random, redrawn, or swapped seat by
 * seat. How sharp they play lives on the Characters page (see tuning.ts). */
import { drawCast, type CharacterId, type Traits } from "../cast";
import type { Difficulty } from "./tuning";

export type LobbySettings = {
  name: string;
  cast: CharacterId[]; // the AI seats, in order around the table
  roles: { jester: boolean; bodyguard: boolean };
};

export const MIN_AI = 4;
export const MAX_AI = 8;

export const DEFAULT_LOBBY: LobbySettings = { name: "", cast: drawCast(6), roles: { jester: false, bodyguard: false } };

/** Saved settings from before the table was always shown: a random table ("Auto") had only a seat count. */
export function fromSaved(saved: Partial<LobbySettings> & { chooseCast?: boolean; opponents?: number }): LobbySettings {
  const s = { ...DEFAULT_LOBBY, ...saved };
  const cast = saved.chooseCast === false ? drawCast(saved.opponents ?? 6) : s.cast;
  return { name: s.name, cast, roles: s.roles };
}

/** Mafia hiding at a table of n players, matching the engine (1 up to 6 players, then 2). */
export const mafiaCount = (players: number) => (players <= 6 ? 1 : 2);

/** The new-game request: every seat, and every seat's knobs as tuned on the Characters page. */
export function newGameRequest(s: LobbySettings, auto: boolean, difficulty: Difficulty, traits: Partial<Record<CharacterId, Traits>>) {
  const roles = (Object.keys(s.roles) as (keyof LobbySettings["roles"])[]).filter((r) => s.roles[r]);
  return { name: s.name.trim(), auto, difficulty, roles, cast: s.cast, traits };
}
