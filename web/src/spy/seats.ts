import { isCharacterId, type CharacterId } from "../cast";
import type { SpyStatus } from "./types";

export type SpySeat = {
  id: string;
  name: string;
  you: boolean;
  character: CharacterId | null;
  role: string | null;
  alive: boolean; // false: voted out
};

export function spySeats(status: SpyStatus): SpySeat[] {
  return status.players.map((p) => {
    const c = status.characters?.[p.id];
    const character = isCharacterId(c) ? c : null;
    return { id: p.id, name: p.name, you: p.id === status.you, character, role: p.role, alive: p.alive !== false };
  });
}

export const nameOf = (seats: SpySeat[], pid: string | null | undefined, you = "You") => {
  const s = seats.find((x) => x.id === pid);
  return s ? (s.you ? you : s.name) : "?";
};
