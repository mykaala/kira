/** Out of Place lobby settings, saved in the browser. */
import type { CharacterId } from "../cast";

export type SpyRolePick = "random" | "spy" | "civilian";

export type SpyLobbySettings = {
  name: string;
  players: number; // you included
  role: SpyRolePick;
  chooseCast: boolean;
  cast: CharacterId[]; // the AI seats when chosen
  roles: boolean; // Advanced: civilians get a secret role at the place
  askAngle: boolean; // Advanced: each AI question gets a seeded topic
};

export const DEFAULT_SPY_LOBBY: SpyLobbySettings = {
  name: "",
  players: 6,
  role: "random",
  chooseCast: false,
  cast: ["ines", "bram", "odile", "tobiah", "kit"],
  roles: true,
  askAngle: false,
};

export const MIN_PLAYERS = 5;
export const MAX_PLAYERS = 8;

export function newSpyGameRequest(s: SpyLobbySettings, auto: boolean) {
  const base = { name: s.name.trim(), players: s.players, role: s.role, auto, roles: s.roles, ask_angle: s.askAngle };
  return s.chooseCast ? { ...base, cast: s.cast.slice(0, s.players - 1) } : base;
}
