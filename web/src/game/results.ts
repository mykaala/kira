/** What the results screen says, worked out from the full event log revealed at game end. */
import type { GameEvent, Status } from "../types";
import type { Seat } from "./model";

export type Fate = { how: "killed" | "voted"; day: number } | null;
export type Sticker = { label: string; color: string };

export type Summary = {
  won: boolean;
  kicker: string;
  headline: string;
  fates: Record<string, Fate>;
  mvp: string | null;
  quote: { pid: string; day: number; text: string } | null;
  stickers: Sticker[];
};

export function summarize(status: Status, seats: Seat[], events: GameEvent[]): Summary {
  const role = (pid: string | null) => seats.find((s) => s.id === pid)?.role;
  const me = seats.find((s) => s.you)!;
  const won = status.winner === status.team;
  const lastDay = status.day;

  const fates: Record<string, Fate> = {};
  for (const e of events) {
    if (e.kind === "morning" && e.target) fates[e.target] = { how: "killed", day: e.day };
    if (e.kind === "elimination" && e.target) fates[e.target] = { how: "voted", day: e.day };
  }

  const votes = events.filter((e) => e.kind === "vote" && e.actor);
  const says = events.filter((e) => e.kind === "say" && e.actor);
  const aiSeats = seats.filter((s) => !s.you);

  // MVP: the jester if they won; for a town win, the AI who voted for mafia most often; else the busiest mafia talker
  let mvp: string | null = null;
  if (status.winner === "jester") {
    mvp = seats.find((x) => x.role === "jester" && !x.you)?.id ?? null; // fooled everyone
  } else if (status.winner === "village") {
    const hits = (pid: string) => votes.filter((v) => v.actor === pid && role(v.target) === "mafia").length;
    mvp = [...aiSeats].sort((a, b) => hits(b.id) - hits(a.id))[0]?.id ?? null;
    if (mvp && hits(mvp) === 0) mvp = null;
  } else {
    const talk = (pid: string) => says.filter((e) => e.actor === pid).length;
    mvp = aiSeats.filter((s) => s.role === "mafia").sort((a, b) => talk(b.id) - talk(a.id))[0]?.id ?? null;
  }

  // the turning point: the day the first mafia member was voted out (town), or the last day (mafia, jester)
  const firstCatch = events.find((e) => e.kind === "elimination" && e.target && role(e.target) === "mafia");
  const turningDay = status.winner === "village" && firstCatch ? firstCatch.day : lastDay;
  const quoteEvent = mvp
    ? [...says].reverse().find((e) => e.actor === mvp && e.day <= turningDay) ?? [...says].reverse().find((e) => e.actor === mvp)
    : null;
  const quote = quoteEvent ? { pid: quoteEvent.actor!, day: quoteEvent.day, text: quoteEvent.text } : null;

  // stickers for you
  const stickers: Sticker[] = [];
  const mine = events.filter((e) => e.vis === `private:${me.id}`);
  if (me.role === "doctor") {
    const saves = mine.filter((e) => {
      if (e.kind !== "result" || !e.target) return false;
      const attack = events.find((m) => m.kind === "mafia_choice" && m.day === e.day);
      return attack?.target === e.target;
    }).length;
    if (saves) stickers.push({ label: `Lifesaver · ${saves} ${saves === 1 ? "save" : "saves"}`, color: "var(--teal)" });
  }
  if (me.role === "detective") {
    const found = mine.filter((e) => e.kind === "result" && /MAFIA/.test(e.text)).length;
    if (found) stickers.push({ label: `Bloodhound · ${found} found`, color: "var(--lavender)" });
  }
  if (me.role === "mafia") {
    const kills = events.filter((e) => e.kind === "morning" && e.target).length;
    if (kills) stickers.push({ label: `Lights out · ${kills} ${kills === 1 ? "kill" : "kills"}`, color: "var(--coral)" });
  }
  const myVotes = votes.filter((v) => v.actor === me.id && v.target);
  if (me.role !== "mafia" && myVotes.length) {
    const good = myVotes.filter((v) => role(v.target) === "mafia").length;
    if (good) stickers.push({ label: `Sharp eye · ${good}/${myVotes.length} votes`, color: "var(--lantern)" });
  }
  if (!votes.some((v) => v.target === me.id)) stickers.push({ label: "Never suspected", color: "var(--lavender)" });
  if (me.alive) stickers.push({ label: "Survivor", color: "var(--teal)" });

  const doctorSaved = stickers.some((s) => s.label.startsWith("Lifesaver"));
  let headline: string;
  if (status.winner === "jester") {
    headline = won ? "They voted you out. You win." : "The jester fooled everyone.";
  } else if (status.winner === "village") {
    headline = won
      ? doctorSaved ? "The sun comes up. Everyone you saved is still here." : "The sun comes up. The town is safe."
      : "Caught. The town wins this one.";
  } else {
    headline = won ? "The town never saw it coming." : "The lantern goes out. The mafia take the town.";
  }

  return {
    won,
    kicker: `${{ village: "Town wins", mafia: "Mafia wins", jester: "Jester wins" }[status.winner ?? ""] ?? "Game over"} · Day ${lastDay}`,
    headline,
    fates,
    mvp,
    quote,
    stickers,
  };
}
