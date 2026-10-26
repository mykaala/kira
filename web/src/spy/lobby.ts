/** Out of Place lobby settings, saved in the browser. Like Mafia, the table is always a real cast you can see. */
import { drawCast, type CharacterId } from "../cast";

export type SpyRolePick = "random" | "spy" | "civilian";

export type SpyLobbySettings = {
  name: string;
  players: number; // you included
  role: SpyRolePick;
  cast: CharacterId[]; // the AI seats: always players - 1 of them
  roles: boolean; // civilians get a secret role at the place
  askAngle: boolean; // each AI question gets a seeded topic
};

export const MIN_PLAYERS = 5;
export const MAX_PLAYERS = 8;

export const DEFAULT_SPY_LOBBY: SpyLobbySettings = {
  name: "",
  players: 6,
  role: "random",
  cast: drawCast(5),
  roles: true,
  askAngle: false,
};

/** Saved settings from before the table was always shown, where a random table ("chooseCast" off) had no cast.
 * Also keeps the cast the right size for the player count. */
export function fromSavedSpy(saved: Partial<SpyLobbySettings> & { chooseCast?: boolean }): SpyLobbySettings {
  const s = { ...DEFAULT_SPY_LOBBY, ...saved };
  const ai = s.players - 1;
  let cast = saved.chooseCast === false ? drawCast(ai) : s.cast.slice(0, ai);
  if (cast.length < ai) cast = [...cast, ...drawCast(8).filter((c) => !cast.includes(c))].slice(0, ai); // fill at random
  return { name: s.name, players: s.players, role: s.role, cast, roles: s.roles, askAngle: s.askAngle };
}

export function newSpyGameRequest(s: SpyLobbySettings, auto: boolean) {
  return {
    name: s.name.trim(), players: s.players, role: s.role, auto, roles: s.roles, ask_angle: s.askAngle,
    cast: s.cast.slice(0, s.players - 1),
  };
}
