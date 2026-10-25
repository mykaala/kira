/** The recurring cast's look. Who they are (voice, quote, traits) comes from the server's
 * /api/cast; this file holds only what the UI draws. Ids match backend/src/agents/personas.py. */

export const CHARACTER_IDS = ["ines", "bram", "odile", "tobiah", "kit", "marguerite", "juno", "hollis"] as const;
export type CharacterId = (typeof CHARACTER_IDS)[number];

export type Traits = { talkative: number; suspicious: number; liar: number };
export type Character = {
  id: CharacterId;
  name: string;
  full_name: string;
  voice: string;
  quote: string;
  traits: Traits;
};

/** Signature colour: the portrait backdrop and the dot beside their lines in the log. */
export const CHARACTER_COLOR: Record<CharacterId, string> = {
  ines: "#5CC8B8",
  bram: "#FF7A59",
  odile: "#9B8BD9",
  tobiah: "#FFB547",
  kit: "#E86FA8",
  marguerite: "#8FB573",
  juno: "#6FA8E8",
  hollis: "#B8ADCB",
};

export const isCharacterId = (id: string | undefined | null): id is CharacterId =>
  !!id && (CHARACTER_IDS as readonly string[]).includes(id);
