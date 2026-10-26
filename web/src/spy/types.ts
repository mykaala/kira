/** Out of Place: what the server sends about a game, from your seat only. */
import type { GameEvent } from "../types";

export type SpyTurnType = "ask" | "answer" | "vote" | "revote" | "last_chance";

export type SpyTurn = {
  type: SpyTurnType;
  targets: string[]; // player ids you may pick (ask, vote, revote)
  can_guess: boolean; // the spy may name the place instead of asking or answering
  prompt: string;
};

export type SpyStatus = {
  mode: "spy_location";
  title: string;
  you: string;
  role: "spy" | "civilian";
  players: { id: string; name: string; role: string | null; alive: boolean }[]; // out: role shows "civilian"
  phase: string; // deal, ask, answer, vote, revote, last_chance
  winner: "spy" | "civilians" | "draw" | null;
  over: boolean;
  ended: string | null; // no result: why
  end_text: string | null;
  turn: SpyTurn | null;
  waiting_on_you: boolean;
  can_guess: boolean; // you're the spy and questions are under way: you may name the place, on anyone's turn
  asker: string | null;
  answerer: string | null;
  revote_between: string[];
  asked: Record<string, number>;
  answered: Record<string, number>;
  questions: number; // this round's
  questions_total: number;
  round: number;
  votes_survived: number;
  survive_votes: number; // the spy wins after surviving this many votes
  ghost: boolean; // you were voted out: watching to the end
  characters: Record<string, string>; // seat id -> cast id
  auto: boolean;
  waiting_for_next: boolean;
  secret: { place: string; role?: SpyRoleCard } | { spy: true };
  notices: string[];
  rules: string;
};

/** A civilian's own role at the place (games with roles on). Never anyone else's during play. */
export type SpyRoleCard = { title: string; wears: string; does: string; deals_with: string };

export type SpyGuess = { kind: "guess" | "last_guess"; guess: string; rule: string; reason: string; match: boolean };

/** One round's vote, its revote, and who went out (a civilian), if anyone. */
export type SpyRound = { round: number; votes: Record<string, number>; revotes: Record<string, number>; out: string | null };

/** Everything, once the game is over. */
export type SpyReveal = {
  events: GameEvent[];
  roles: Record<string, string>;
  place_roles: Record<string, string>; // seat id -> role title at the place (roles on; empty otherwise)
  place: string;
  spy: string;
  voices: Record<string, string>;
  votes: Record<string, number>; // the last vote's tally
  revotes: Record<string, number>;
  rounds: SpyRound[];
  survive_votes: number;
  guesses: SpyGuess[];
  end_text: string | null;
  winner: SpyStatus["winner"];
  ended: string | null;
  places: string[];
};

export type SpyConfig = { title: string; min_players: number; max_players: number; places: string[] };

export type SpyMove =
  | { type: "ask"; target: string; text: string; confirm?: boolean }
  | { type: "answer"; text: string; confirm?: boolean }
  | { type: "vote"; target: string }
  | { type: "guess"; text: string };

/** How the rules engine words why a guess was ruled the way it was. */
export const RULE_LABEL: Record<string, string> = {
  exact: "the place's name",
  alias: "another name for the place",
  modifier: "the place's name, with a describing word",
  typo: "the place's name, with a typo",
  other_place: "a different place",
  partial: "only part of the place's name",
  judge: "decided by the judge",
  judge_memo: "decided by the judge (remembered)",
  judge_failed: "the judge couldn't decide, so it didn't count",
};

export const MAX_WORDS = 25;
export const MAX_GUESS_WORDS = 6; // a guess names one place
export const MAX_CHARS = 200;
export const wordCount = (t: string) => (t.trim() ? t.trim().split(/\s+/).length : 0);
