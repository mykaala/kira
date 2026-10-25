import { useEffect, useRef, useState } from "react";
import type { GameEvent, Status } from "./types";

export type Speed = "slow" | "normal" | "fast";

// Pause after each kind of event, in ms at normal speed. Everything waits its turn in one queue,
// so a vote, a death or a new phase gets a beat before the next thing appears.
const GAP_MS: Record<string, number> = {
  say: 900,
  vote: 1500,
  elimination: 3000,
  morning: 3000,
  phase: 2200,
  result: 1800,
  mafia_choice: 1800,
};
const DEFAULT_GAP_MS = 400;
const SPEED: Record<Speed, { gap: number; cps: number }> = {
  slow: { gap: 1.6, cps: 18 },
  normal: { gap: 1, cps: 28 },
  fast: { gap: 0.4, cps: 70 },
};
const TICK_MS = 40;

/** Subscribes to a game's SSE stream and plays it back at a readable pace: AI messages are typed
 * out, and votes, deaths and phase changes are revealed one at a time. History replayed on
 * (re)connect appears instantly. */
export function useGame(gameId: string | null, speed: Speed = "normal") {
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({}); // "" = typing indicator
  const [acted, setActed] = useState<Set<string>>(new Set());
  const [reveal, setReveal] = useState<GameEvent[] | null>(null);
  const [gone, setGone] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const queue = useRef<GameEvent[]>([]);
  const seen = useRef<Set<number>>(new Set()); // a reconnect replays history; show each event once
  const pendingStatus = useRef<Status | null>(null);
  const timer = useRef<number | null>(null);
  const live = useRef(false); // false while the history replay is arriving
  const replayed = useRef<Set<number>>(new Set()); // history events: shown instantly
  const speedRef = useRef(SPEED[speed]);
  speedRef.current = SPEED[speed];

  useEffect(() => {
    if (!gameId) return;
    setEvents([]);
    setStatus(null);
    setDrafts({});
    setReveal(null);
    setGone(false);
    setFailure(null);
    queue.current = [];
    seen.current = new Set();
    live.current = false;
    replayed.current = new Set();

    const show = (e: GameEvent) => {
      setEvents((es) => [...es, e]);
      if (e.kind === "say" && e.actor) setDrafts(({ [e.actor!]: _, ...rest }) => rest);
      if (e.kind === "phase") setActed(new Set());
    };
    const after = (e: GameEvent) => {
      const gap = replayed.current.has(e.seq) ? 0 : (GAP_MS[e.kind] ?? DEFAULT_GAP_MS) * speedRef.current.gap;
      timer.current = window.setTimeout(drain, gap);
    };
    const typeOut = (e: GameEvent) => {
      let shown = 0;
      const step = () => {
        shown += Math.max(1, Math.round((speedRef.current.cps * TICK_MS) / 1000));
        if (shown >= e.text.length) {
          show(e);
          after(e);
          return;
        }
        setDrafts((d) => ({ ...d, [e.actor!]: e.text.slice(0, shown) }));
        timer.current = window.setTimeout(step, TICK_MS);
      };
      step();
    };
    const drain = () => {
      timer.current = null;
      const next = queue.current.shift();
      if (!next) {
        if (pendingStatus.current) setStatus(pendingStatus.current);
        return;
      }
      const you = pendingStatus.current?.you;
      if (!replayed.current.has(next.seq) && next.kind === "say" && next.actor && next.actor !== you) {
        typeOut(next);
        return;
      }
      show(next);
      after(next);
    };
    const kick = () => {
      if (timer.current === null) drain();
    };

    const es = new EventSource(`/api/games/${gameId}/events`);
    es.addEventListener("event", (m) => {
      const e: GameEvent = JSON.parse((m as MessageEvent).data);
      if (seen.current.has(e.seq)) return;
      seen.current.add(e.seq);
      if (!live.current) replayed.current.add(e.seq);
      queue.current.push(e);
      kick();
    });
    es.addEventListener("status", (m) => {
      pendingStatus.current = JSON.parse((m as MessageEvent).data);
      live.current = true; // the server sends history first, then a status
      kick();
    });
    es.addEventListener("typing", (m) => {
      const { pid } = JSON.parse((m as MessageEvent).data);
      setDrafts((d) => (pid in d ? d : { ...d, [pid]: "" }));
    });
    // raw model output streams in as deltas; the final, cleaned-up message is typed out instead
    es.addEventListener("retract", (m) => {
      const { pid } = JSON.parse((m as MessageEvent).data);
      setDrafts((d) => (d[pid] === "" ? (({ [pid]: _, ...rest }) => rest)(d) : d));
    });
    es.onerror = () => {
      // a 404 (unknown game) closes the stream for good; network blips reconnect on their own
      if (es.readyState === EventSource.CLOSED) setGone(true);
    };
    es.addEventListener("error", (m) => {
      // the server's own "error" event (an SSE event named error), not a connection error
      const data = (m as MessageEvent).data;
      if (data) setFailure(JSON.parse(data).message);
    });
    es.addEventListener("reveal", (m) => {
      setReveal(JSON.parse((m as MessageEvent).data).events);
    });
    es.addEventListener("acted", (m) => {
      const { pid } = JSON.parse((m as MessageEvent).data);
      setActed((s) => new Set(s).add(pid));
    });
    return () => {
      es.close();
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = null;
    };
  }, [gameId]);

  return { events, status, drafts, acted, reveal, gone, failure };
}

export async function post(path: string, body: unknown, timeoutMs = 10000) {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new Error("The game server isn't answering. Is the backend running? Restart it and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? `Server error (${res.status})`);
  return data;
}
