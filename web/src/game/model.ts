/** Derived views of the game for the table: seats, who is on stage, who leans towards whom.
 * Everything here comes from what the player is allowed to see. */
import { isCharacterId, type CharacterId } from "../cast";
import type { GameEvent, Status } from "../types";

export type Seat = {
  id: string;
  name: string;
  alive: boolean;
  role: string | null;
  you: boolean;
  character: CharacterId | null; // null for the human
};

export function seatsOf(status: Status): Seat[] {
  return status.players.map((p) => {
    const c = status.characters?.[p.id];
    return {
      id: p.id,
      name: p.name,
      alive: p.alive,
      role: p.role,
      you: p.id === status.you,
      character: isCharacterId(c) ? c : null,
    };
  });
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Seats named in a message, in the order they appear. */
export function namedIn(text: string, seats: Seat[], exclude?: string): string[] {
  const hits: [number, string][] = [];
  for (const s of seats) {
    if (s.id === exclude) continue;
    const m = new RegExp(`\\b${escape(s.name)}\\b`, "i").exec(text);
    if (m) hits.push([m.index, s.id]);
  }
  return hits.sort((a, b) => a[0] - b[0]).map(([, id]) => id);
}

export const saysOn = (events: GameEvent[], day: number) =>
  events.filter((e) => e.kind === "say" && e.day === day && e.actor);

/** Who each player is leaning towards today: the first person named in their latest message
 * that names anyone. Public chat only, never an AI's private notes. */
export type StageLine = { pid: string; text: string; typing: boolean; seq: number | null };

/** The one line on stage: a message being typed out, someone about to speak, or the last one said. */
export function stageLine(events: GameEvent[], drafts: Record<string, string>, day: number): StageLine | null {
  const writing = Object.entries(drafts).find(([, t]) => t);
  if (writing) return { pid: writing[0], text: writing[1], typing: true, seq: null };
  const waiting = Object.keys(drafts)[0];
  if (waiting) return { pid: waiting, text: "", typing: true, seq: null };
  const last = [...saysOn(events, day)].pop();
  return last ? { pid: last.actor!, text: last.text, typing: false, seq: last.seq } : null;
}

/** Whom a line answers: the first player it names, otherwise the previous speaker. */
export function replyingTo(line: StageLine, events: GameEvent[], seats: Seat[], day: number): string | null {
  const named = namedIn(line.text, seats, line.pid)[0];
  if (named) return named;
  const says = saysOn(events, day).filter((e) => e.seq !== line.seq);
  const before = line.seq === null ? says : says.filter((e) => e.seq < line.seq!);
  const prev = [...before].reverse().find((e) => e.actor !== line.pid);
  return prev?.actor ?? null;
}

export function moodOf(line: StageLine): "speaking" | "angry" | "smug" | "neutral" {
  if (line.typing) return "speaking";
  if (/!|\b[A-Z]{2,}\b/.test(line.text)) return "angry";
  if (/\b(lol|lmao|haha|jk|ngl)\b/i.test(line.text)) return "smug";
  return "neutral";
}

export const ROLE_COLOR: Record<string, string> = {
  mafia: "var(--coral)",
  detective: "var(--lavender)",
  doctor: "var(--teal)",
  villager: "var(--text)",
  jester: "var(--pink)",
  bodyguard: "var(--sky)",
};

/** Roles a player could claim or guess in this game: the usual three plus any optional ones dealt. */
export function rolesInPlay(status: Status, opts: { withMafia?: boolean } = {}): string[] {
  const roles = ["villager", "doctor", "detective", ...(status.house?.roles ?? [])];
  return opts.withMafia ? [...roles, "mafia"] : roles;
}
