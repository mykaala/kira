"""One logger: every model call records tokens, dollars and latency, plus full I/O for replay."""

import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY, mode TEXT, seed INTEGER, players TEXT, human INTEGER,
    started_at REAL, ended_at REAL, winner TEXT, days INTEGER
);
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY, game_id TEXT, player TEXT, call_type TEXT, model TEXT, attempt INTEGER,
    input_tokens INTEGER, cached_tokens INTEGER, output_tokens INTEGER, cost_usd REAL,
    ttft_ms REAL, latency_ms REAL, valid INTEGER, error TEXT, prompt TEXT, response TEXT, created_at REAL,
    ref_flag INTEGER DEFAULT 0, timed_out INTEGER DEFAULT 0, reasoning_tokens INTEGER DEFAULT 0, flag_reason TEXT,
    accuse_mismatch INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY, game_id TEXT, day INTEGER, phase TEXT, calls INTEGER, latency_ms REAL, created_at REAL
);
"""


def cost_usd(
    prices: dict[str, tuple[float, float, float]], model: str, input_tokens: int, cached_tokens: int, output_tokens: int
) -> float:
    p_in, p_out, p_cached = prices.get(model, (0.0, 0.0, 0.0))
    return ((input_tokens - cached_tokens) * p_in + cached_tokens * p_cached + output_tokens * p_out) / 1e6


class CostLog:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        cols = {row[1] for row in self.db.execute("PRAGMA table_info(calls)")}
        added = {
            "ref_flag": "INTEGER DEFAULT 0",
            "timed_out": "INTEGER DEFAULT 0",
            "reasoning_tokens": "INTEGER DEFAULT 0",
            "flag_reason": "TEXT",
            "accuse_mismatch": "INTEGER DEFAULT 0",
        }
        for col, kind in added.items():  # databases from before these columns existed
            if col not in cols:
                self.db.execute(f"ALTER TABLE calls ADD COLUMN {col} {kind}")

    def game_started(self, game_id: str, mode: str, seed: int, players: list[dict], human: bool) -> None:
        self.db.execute(
            "INSERT INTO games (id, mode, seed, players, human, started_at) VALUES (?,?,?,?,?,?)",
            (game_id, mode, seed, json.dumps(players), int(human), time.time()),
        )
        self.db.commit()

    def game_ended(self, game_id: str, winner: str | None, days: int) -> None:
        self.db.execute(
            "UPDATE games SET ended_at=?, winner=?, days=? WHERE id=?", (time.time(), winner, days, game_id)
        )
        self.db.commit()

    def call(self, **row) -> None:
        row["created_at"] = time.time()
        cols = ", ".join(row)
        self.db.execute(f"INSERT INTO calls ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
        self.db.commit()

    def round(self, game_id: str, day: int, phase: str, calls: int, latency_ms: float) -> None:
        self.db.execute(
            "INSERT INTO rounds (game_id, day, phase, calls, latency_ms, created_at) VALUES (?,?,?,?,?,?)",
            (game_id, day, phase, calls, latency_ms, time.time()),
        )
        self.db.commit()
