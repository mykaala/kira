"""Who speaks in a discussion. Round 1: every living player once, in a seeded order.
Later rounds: a few extra speakers, those accused or addressed first."""

import re
from collections import Counter

from .models import Event, GameState


def round_one_order(state: GameState) -> list[str]:
    ids = [p.id for p in state.alive()]
    state.rng("round-one").shuffle(ids)
    return ids


def _says_today(state: GameState) -> list[Event]:
    return [e for e in state.events if e.kind == "say" and e.day == state.day and e.phase == state.phase]


def extra_speakers(state: GameState, count: int, exclude: tuple[str, ...] = ()) -> list[str]:
    """AI players named in the latest message first, then the most-named today, then random."""
    pool = [p for p in state.alive() if not p.is_human and p.id not in exclude]
    order = {p.id: i for i, p in enumerate(state.players)}
    says = _says_today(state)

    def named_in(e: Event) -> list[str]:
        return [p.id for p in pool if p.id != e.actor and re.search(rf"\b{re.escape(p.name)}\b", e.text, re.I)]

    latest = named_in(says[-1]) if says else []
    counts = Counter(pid for e in says for pid in named_in(e))
    ranked = latest + sorted((pid for pid in counts if pid not in latest), key=lambda pid: (-counts[pid], order[pid]))
    rest = [p.id for p in pool if p.id not in ranked]
    state.rng("extra").shuffle(rest)
    picked = (ranked + rest)[:count]

    # nobody speaks twice in a row
    last = says[-1].actor if says else None
    if len(picked) > 1 and picked[0] == last:
        picked[0], picked[1] = picked[1], picked[0]
    return picked
