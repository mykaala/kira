"""Game-balance and voice metrics for self-play runs. Works on a plain "record" (roles by name
plus the full event list by name), built either from a live GameState or, for older runs, parsed
back out of the saved text transcript."""

import re
from collections import Counter

from engine.models import GameState

# --- the record -----------------------------------------------------------------------------


def record_of(state: GameState) -> dict:
    names = {p.id: p.name for p in state.players}
    nm = lambda pid: names.get(pid) if pid else None  # noqa: E731
    claims = getattr(state, "claims", None)
    return {
        "roles": {p.name: p.role for p in state.players},
        "winner": state.winner,
        "days": state.day,
        "events": [
            {
                "day": e.day,
                "phase": e.phase,
                "kind": e.kind,
                "text": e.text,
                "vis": e.vis,
                "actor": nm(e.actor),
                "target": nm(e.target),
            }
            for e in state.events
        ],
        "claims": None
        if claims is None
        else [
            {
                "seq": c.seq,
                "day": c.day,
                "actor": nm(c.actor),
                "role": c.role,
                "target": nm(c.target),
                "result": c.result,
                "true": c.true,
            }
            for c in claims
        ],
    }


_PHASE = re.compile(r"^=== Day (\d+): (\w+) ===$")
_SAY = re.compile(r"^  (\S+) \((\w+)\): (.*)$")
_SYS = re.compile(r"^  · (?:\[([^\]]+)\] )?(.*)$")
_PATTERNS = [  # (kind, regex with actor/target groups) for the engine's fixed event texts
    ("result", re.compile(r"^Your investigation: (?P<target>\S+) is (?:MAFIA|not mafia)\.$")),
    ("result", re.compile(r"^You (?:protected|guarded) (?P<target>\S+) tonight\.$")),
    ("mafia_choice", re.compile(r"^The mafia chose (?P<target>\S+)\.$")),
    ("vote", re.compile(r"^(?P<actor>\S+) voted for (?P<target>\S+)\.$")),
    ("vote", re.compile(r"^(?P<actor>\S+) abstained\.$")),
    ("elimination", re.compile(r"^(?:(?P<target>\S+) was eliminated\..*|No one was eliminated\.)$")),
    ("morning", re.compile(r"^(?:(?P<target>\S+) was killed in the night\..*|No one died\.|Day 1 begins\..*)$")),
    ("game_over", re.compile(r"^The \w+ wins! .*$")),
]


def parse_transcript(summary: dict) -> dict:
    """A record rebuilt from an older run's text transcript (secrets included)."""
    roles: dict[str, str] = {}
    events, day, phase = [], 0, ""
    for line in summary["transcript"]:
        if m := _PHASE.match(line):
            day, phase = int(m[1]), m[2]
            events.append(
                {
                    "day": day,
                    "phase": phase,
                    "kind": "phase",
                    "text": line,
                    "vis": "public",
                    "actor": None,
                    "target": None,
                }
            )
        elif m := _SAY.match(line):
            roles[m[1]] = m[2]
            events.append(
                {
                    "day": day,
                    "phase": phase,
                    "kind": "say",
                    "text": m[3],
                    "vis": "public",
                    "actor": m[1],
                    "target": None,
                }
            )
        elif m := _SYS.match(line):
            vis, text = m[1] or "public", m[2]
            for kind, rx in _PATTERNS:
                if hit := rx.match(text):
                    g = hit.groupdict()
                    events.append(
                        {
                            "day": day,
                            "phase": phase,
                            "kind": kind,
                            "text": text,
                            "vis": vis,
                            "actor": g.get("actor"),
                            "target": g.get("target"),
                        }
                    )
                    break
            if text.startswith("The ") and " wins! " in text:
                for name, role in re.findall(r"(\S+) was (\w+)", text.split(" wins! ", 1)[1]):
                    roles[name] = role
    return {"roles": roles, "winner": summary["winner"], "days": summary["days"], "events": events, "claims": None}


# --- claims ---------------------------------------------------------------------------------

# Used only when a record has no structured claims (runs from before the claim field existed).
_CLAIM = re.compile(
    r"\b(?:i'?m|im|i am)\s+(?:the\s+|actually\s+|literally\s+|real\s+)*(?:detective|cop)\b"
    r"|\b(?:detective|cop)\s+here\b|\bi\s+(?:checked|investigated)\b|\bmy\s+(?:check|investigation)\b",
    re.I,
)
_CLEAR = r"(?:not\s+mafia|clear(?:ed)?|innocent|town|good)"


def _claim_target(text: str, speaker: str, names: list[str]) -> tuple[str | None, str | None]:
    """Best-effort target and result: "kofi is mafia", "checked kofi. not mafia", "sasha, i checked you"."""
    alt = "|".join(re.escape(n) for n in names if n != speaker)
    if m := re.search(rf"\b({alt})\b\s+(?:is|was|=)\s+(?:\w+\s+)?({_CLEAR}|mafia)\b", text, re.I):
        return m[1], "mafia" if m[2].lower() == "mafia" else "not mafia"
    if m := re.search(rf"\b(?:checked|investigated)\s+({alt}|you|him|her)\b", text, re.I):
        target = m[1]
        if target.lower() in ("you", "him", "her"):
            first = re.match(rf"^\s*({alt})\b", text, re.I)
            target = first[1] if first else None
        rest = text[m.end() :]
        result = (
            "not mafia"
            if re.search(rf"\b{_CLEAR}\b", rest, re.I)
            else "mafia"
            if re.search(r"\bmafia\b", rest, re.I)
            else None
        )
        return target and next(n for n in names if n.lower() == target.lower()), result
    return None, None


def text_claims(rec: dict) -> list[dict]:
    """Detective claims found in message text, with the named target and result when legible."""
    out = []
    for e in rec["events"]:
        if e["kind"] != "say" or not _CLAIM.search(e["text"]):
            continue
        target, result = _claim_target(e["text"], e["actor"], list(rec["roles"]))
        if target:
            target = next(n for n in rec["roles"] if n.lower() == target.lower())
        out.append(
            {
                "day": e["day"],
                "actor": e["actor"],
                "role": "detective",
                "target": target,
                "result": result,
                "true": rec["roles"].get(e["actor"]) == "detective",
            }
        )
    return out


def claims_of(rec: dict) -> list[dict]:
    return rec["claims"] if rec["claims"] is not None else text_claims(rec)


# --- voice ----------------------------------------------------------------------------------

PHRASES = {  # the shared vocabulary from the 20-game read
    "convenient": r"\bconvenient(?:ly)?\b",
    "too neat": r"\btoo neat\b",
    "staged": r"\bstag(?:ed|ing|e)\b",
    "reeks": r"\breek(?:s|ing|ed)?\b",
    "leap": r"\bleap(?:s|ing|ed|t)?\b",
    "proves nothing": r"\bprov(?:es|ed|ing) nothing\b",
    "lazy": r"\blazy\b",
    "tidy": r"\btid(?:y|ier|iest)\b",
    "pile-on": r"\bpil(?:e|ing)[- ]?on\b|\bdog[- ]?pil(?:e|ed|ing)\b",
    "tell": r"\btells?\b(?!\s+(?:me|us|you|him|her|them|everyone)\b)",
    "easy": r"\beas(?:y|ier|iest)\b",
}
_PHRASE_RX = {k: re.compile(v, re.I) for k, v in PHRASES.items()}
_WORD = re.compile(r"[a-z0-9']+")


def phrase_uses(text: str) -> list[str]:
    return [k for k, rx in _PHRASE_RX.items() for _ in rx.finditer(text)]


def voice_metrics(says: list[dict]) -> dict:
    per_player: dict[str, Counter] = {}
    totals: Counter = Counter()
    bigrams: list[tuple[str, str]] = []
    with_phrase = 0
    for e in says:
        uses = phrase_uses(e["text"])
        with_phrase += bool(uses)
        per_player.setdefault(e["actor"], Counter()).update(uses)
        totals.update(uses)
        words = _WORD.findall(e["text"].lower())
        bigrams += list(zip(words, words[1:]))
    repeats = sum(c - 1 for counts in per_player.values() for c in counts.values() if c > 1)
    return {
        "messages": len(says),
        "phrase_uses": dict(totals),
        "messages_with_phrase": with_phrase,
        "repeated_phrase_uses": repeats,  # a phrase used again by the same player in the same game
        "bigrams": len(bigrams),
        "distinct_bigrams": len(set(bigrams)),
    }


# --- per game -------------------------------------------------------------------------------

_DAY1_DEATH_TALK = re.compile(
    r"\bno (?:one|body)?\s*(?:died|dead|death|kill|killed)\b|\bnobody died\b|\bno deaths?\b|\bno kill\b"
    r"|\bno body\b|\bquiet night\b|\bdoctor (?:saved|save|hit)\b|\bmafia (?:stalled|skipped|missed)\b|\bclean night\b",
    re.I,
)


def game_metrics(rec: dict) -> dict:
    roles, ev = rec["roles"], rec["events"]
    mafia = {n for n, r in roles.items() if r == "mafia"}
    says = [e for e in ev if e["kind"] == "say"]
    claims = claims_of(rec)

    # the night-1 check and whether it hit
    check = next(
        (e for e in ev if e["kind"] == "result" and e["text"].startswith("Your investigation") and e["day"] == 1), None
    )
    first_check = None if not check else ("hit" if "MAFIA" in check["text"] else "miss")

    # claims: the first day-1 detective claim, and mafia counterclaims
    det_claims = [c for c in claims if c["role"] == "detective"]
    day1 = next((c for c in det_claims if c["day"] == 1), None)
    counter = False
    for i, c in enumerate(det_claims):
        if roles.get(c["actor"]) == "mafia" and any(o["actor"] != c["actor"] for o in det_claims[:i]):
            counter = True
    first_claim_by = {}
    for c in det_claims:
        first_claim_by.setdefault(c["actor"], c)

    # each mafia bluffer's first detective claim, and what happened to them
    bluffs, seen = [], set()
    for i, c in enumerate(det_claims):
        if roles.get(c["actor"]) != "mafia" or c["actor"] in seen:
            continue
        seen.add(c["actor"])
        kind = "counterclaim" if any(o["actor"] != c["actor"] for o in det_claims[:i]) else "first claim"
        out = next((e for e in ev if e["kind"] == "elimination" and e["target"] == c["actor"]), None)
        fate = "never voted out" if not out else "same day" if out["day"] == c["day"] else "later"
        bluffs.append({"kind": kind, "fate": fate})

    # the first mafia eliminated: when, and whether a detective claim had named them first
    caught = None
    for idx, e in enumerate(ev):
        if e["kind"] == "elimination" and e["target"] in mafia:
            before = [
                c for c in det_claims if c["target"] == e["target"] and c["result"] == "mafia" and c["day"] <= e["day"]
            ]
            caught = {"day": e["day"], "how": "after a detective claim" if before else "vote, no claim"}
            break

    # night kills: attempted, blocked by the doctor, and the doctor's repeat saves
    attempts = [e for e in ev if e["kind"] == "mafia_choice"]
    doc = {n for n, r in roles.items() if r == "doctor"}
    protects = {e["day"]: e["target"] for e in ev if e["kind"] == "result" and e["text"].startswith("You protected")}
    blocked = sum(protects.get(a["day"]) == a["target"] for a in attempts)
    repeats = sum(protects.get(d) is not None and protects.get(d) == protects.get(d - 1) for d in protects)

    # do the mafia vote together?
    together = splits = 0
    for d in sorted({e["day"] for e in ev if e["kind"] == "vote"}):
        mv = [e["target"] for e in ev if e["kind"] == "vote" and e["day"] == d and e["actor"] in mafia and e["target"]]
        if len(mv) >= 2:
            if len(set(mv)) == 1:
                together += 1
            else:
                splits += 1

    return {
        "winner": rec["winner"],
        "days": rec["days"],
        "doctor_alive_n1": bool(doc),
        "first_check": first_check,
        "day1_claim": None
        if not day1
        else {"by": roles.get(day1["actor"]), "true": day1["true"], "target": day1["target"], "result": day1["result"]},
        "detective_claimers": {a: roles.get(a) for a in first_claim_by},
        "mafia_counterclaim": counter,
        "mafia_fake_claim": any(roles.get(c["actor"]) == "mafia" for c in det_claims),
        "bluffs": bluffs,
        "first_mafia_caught": caught,
        "kills_attempted": len(attempts),
        "kills_blocked_by_doctor": blocked,
        "doctor_repeat_saves": repeats,
        "day1_death_talk": any(_DAY1_DEATH_TALK.search(e["text"]) for e in says if e["day"] == 1),
        "mafia_votes_together": together,
        "mafia_votes_split": splits,
        "accusing_messages": sum(bool(e["target"]) for e in says),
        "voice": voice_metrics(says),
    }


def aggregate_metrics(ms: list[dict]) -> dict:
    n = len(ms)
    pct = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    hit = [m for m in ms if m["first_check"] == "hit"]
    miss = [m for m in ms if m["first_check"] != "hit"]
    vwin = lambda xs: sum(m["winner"] == "village" for m in xs)  # noqa: E731
    d1 = [m["day1_claim"] for m in ms if m["day1_claim"]]
    caught = [m["first_mafia_caught"] for m in ms if m["first_mafia_caught"]]
    attempts = sum(m["kills_attempted"] for m in ms)
    blocked = sum(m["kills_blocked_by_doctor"] for m in ms)
    v = [m["voice"] for m in ms]
    msgs = sum(x["messages"] for x in v)
    phrases: Counter = Counter()
    for x in v:
        phrases.update(x["phrase_uses"])
    together = sum(m["mafia_votes_together"] for m in ms)
    split = sum(m["mafia_votes_split"] for m in ms)
    return {
        "games": n,
        "first_check": {
            "hit": len(hit),
            "hit_village_wins": vwin(hit),
            "miss_or_none": len(miss),
            "miss_village_wins": vwin(miss),
        },
        "day1_claim": {
            "games_with_claim": len(d1),
            "true": sum(c["true"] for c in d1),
            "fake": sum(not c["true"] for c in d1),
        },
        "mafia_fake_claim_games": sum(m["mafia_fake_claim"] for m in ms),
        "bluff_survival": {
            kind: dict(Counter(b["fate"] for m in ms for b in m.get("bluffs", []) if b["kind"] == kind))
            for kind in ("first claim", "counterclaim")
        },
        "mafia_counterclaim_games": sum(m["mafia_counterclaim"] for m in ms),
        "first_mafia_caught": {
            "games": len(caught),
            "by_day": dict(sorted(Counter(c["day"] for c in caught).items())),
            "how": dict(Counter(c["how"] for c in caught)),
        },
        "kills": {
            "attempted": attempts,
            "blocked_by_doctor": blocked,
            "blocked_rate": pct(blocked, attempts),
            "doctor_repeat_saves": sum(m["doctor_repeat_saves"] for m in ms),
        },
        "day1_death_talk_games": sum(m["day1_death_talk"] for m in ms),
        "mafia_votes": {"together": together, "split": split, "together_rate": pct(together, together + split)},
        "accusing_message_rate": pct(sum(m.get("accusing_messages", 0) for m in ms), msgs),
        "voice": {
            "messages": msgs,
            "messages_with_phrase_rate": pct(sum(x["messages_with_phrase"] for x in v), msgs),
            "repeated_phrase_rate": pct(sum(x["repeated_phrase_uses"] for x in v), msgs),
            "distinct_bigram_ratio": pct(sum(x["distinct_bigrams"] for x in v), sum(x["bigrams"] for x in v)),
            "phrase_uses": dict(phrases.most_common()),
        },
    }


def format_metrics(a: dict) -> str:
    fc, d1, k, mc, vo, mv = (
        a["first_check"],
        a["day1_claim"],
        a["kills"],
        a["first_mafia_caught"],
        a["voice"],
        a["mafia_votes"],
    )
    rate = lambda x: "n/a" if x is None else f"{x:.0%}"  # noqa: E731
    return "\n".join(
        [
            f"  night-1 check hit mafia: {fc['hit']}/{a['games']} games, village won {fc['hit_village_wins']} of those; "
            f"otherwise village won {fc['miss_village_wins']}/{fc['miss_or_none']}",
            f"  day-1 detective claim: {d1['games_with_claim']} games ({d1['true']} true, {d1['fake']} fake); "
            f"mafia fake-claimed in {a['mafia_fake_claim_games']}, counterclaimed in {a['mafia_counterclaim_games']}",
            "  bluff survival (voted out same day / later / never): "
            + "; ".join(
                f"{k} {v.get('same day', 0)}/{v.get('later', 0)}/{v.get('never voted out', 0)}"
                for k, v in a["bluff_survival"].items()
            ),
            f"  first mafia caught: {mc['games']} games, by day {mc['by_day']}, {mc['how']}",
            f"  night kills: {k['attempted']} attempted, {k['blocked_by_doctor']} blocked by the doctor "
            f"({rate(k['blocked_rate'])}), doctor repeat saves {k['doctor_repeat_saves']}",
            f"  day-1 'no death' talk: {a['day1_death_talk_games']}/{a['games']} games",
            f"  mafia voting together: {mv['together']} of {mv['together'] + mv['split']} votes "
            f"({rate(mv['together_rate'])})",
            f"  messages with a public accusation: {rate(a.get('accusing_message_rate'))}",
            f"  voice: {vo['messages']} messages, {rate(vo['messages_with_phrase_rate'])} use a stock phrase, "
            f"repeated-phrase rate {rate(vo['repeated_phrase_rate'])}, distinct bigrams {rate(vo['distinct_bigram_ratio'])}",
            f"  stock phrases: {vo['phrase_uses']}",
        ]
    )
