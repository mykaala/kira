export type GameEvent = {
  seq: number;
  day: number;
  phase: string;
  kind: string;
  text: string;
  vis: string;
  actor: string | null;
  target: string | null;
};

export type PlayerInfo = { id: string; name: string; alive: boolean; role: string | null };

export type Status = {
  mode: string;
  you: string;
  role: string;
  team: string;
  teammates: string[];
  players: PlayerInfo[];
  day: number;
  phase: string;
  legal_actions: string[];
  winner: string | null;
  waiting_on_you: boolean;
  auto: boolean;
  waiting_for_next: boolean;
  next_speaker: string | null;
  characters: Record<string, string>; // seat id -> cast id
  turns_left: number;
  turns_total: number;
  house: { difficulty: string; roles: string[] }; // optional roles dealt this game
  accusations: Record<string, string>; // public: who each player is pointing at right now
};
