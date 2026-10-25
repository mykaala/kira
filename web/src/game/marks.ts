/** Your private reads on other players: a cue, a role guess and a short note. */
export type Cue = "trust" | "unsure" | "suspect" | "mafia";
export type RoleGuess = string; // detective, doctor, villager, or an optional role in play
export type Mark = { cue?: Cue; role?: RoleGuess; note?: string };
export type Marks = Record<string, Mark>;

export const CUES: { id: Cue; label: string; color: string }[] = [
  { id: "trust", label: "Trust", color: "var(--teal)" },
  { id: "unsure", label: "Unsure", color: "var(--muted)" },
  { id: "suspect", label: "Suspect", color: "var(--lantern)" },
  { id: "mafia", label: "Mafia!", color: "var(--coral)" },
];
export const cueColor = (cue?: Cue) => CUES.find((c) => c.id === cue)?.color;
