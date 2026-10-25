import type { CharacterId } from "../cast";

/** Small physical reactions from the people a line names. Flavour only: picked by code, no model call. */
const REACTIONS: Record<CharacterId, string[]> = {
  ines: ["takes a note", "raises an eyebrow", "taps the table twice"],
  bram: ["crosses arms", "scoffs loudly", "slaps the table"],
  odile: ["stares", "says nothing", "goes very still"],
  tobiah: ["flashes a grin", "laughs it off", "spreads both hands"],
  kit: ["snorts", "grins wider", "mouths “wow”"],
  marguerite: ["tuts softly", "sips tea", "smiles thinly"],
  juno: ["winces", "raises a hand", "sighs"],
  hollis: ["squints", "folds arms", "mutters “prove it”"],
};

export function reactionFor(character: CharacterId, seed: number): string {
  const lines = REACTIONS[character];
  return lines[Math.abs(seed) % lines.length];
}
