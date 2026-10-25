"""Generate the role bank once, offline: ten roles for each of the 40 places (one model call per place, strict
schema), checked in code and retried with the problems spelled out. Writes src/engine/modes/spy_roles.py (plain
data, so the engine reads no files) and docs/spy-roles.md (a table for review). Games never call this script.
`insider_tell` is for review and the consistency judge only; no game prompt may contain it.
python scripts/spy_roles_gen.py [--places "sauna" "ferry"] [--parallel 8]"""

import argparse
import asyncio
import json
import pprint
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agents.costlog import cost_usd  # noqa: E402
from agents.llm import OpenAILLM, Usage  # noqa: E402
from agents.spy_guess import guess_aliases  # noqa: E402
from engine.modes.spy_location import CLUSTER_OF, CLUSTERS, LOCATION_NAMES, LOCATIONS  # noqa: E402
from server.settings import get_settings  # noqa: E402

OUT = ROOT / "src" / "engine" / "modes" / "spy_roles.py"
TABLE = ROOT.parent / "docs" / "spy-roles.md"
FIELDS = ("title", "wears", "does", "deals_with", "insider_tell")
ROLES, MIN_GENERIC, MAX_TITLE_WORDS = 10, 3, 3

# Role names from the published party game we borrowed the mechanic from. Our titles must not copy them. Plain
# job words that are just English (customer, visitor, manager, cashier, nurse, security guard) are not listed:
# the generic roles need them, and they belong to nobody.
BORROWED_TITLES = {
    "first class passenger", "economy class passenger", "air marshal", "stewardess", "co-pilot",
    "armored car driver", "beach waitress", "kite surfer", "beach goer", "beach photographer",
    "ice cream truck driver", "head security guard", "hustler", "unwanted guest", "delivery boy",
    "imprisoned arab", "choir singer", "animal trainer", "fire eater", "government official", "refugee",
    "tank engineer", "stunt man", "camera man", "costume artist", "rich passenger", "border patrol",
    "train attendant", "restaurant chef", "stoker", "cannoneer", "bound prisoner", "cabin boy", "brave captain",
    "expedition leader", "radioman", "criminalist", "archivist", "patrol officer", "food critic", "head chef",
    "gym teacher", "lunch lady", "maintenance man", "tire specialist", "car wash operator", "auto mechanic",
    "space tourist", "sonar technician", "electronics technician", "food sample demonstrator", "shelf stocker",
    "coat check lady", "prompter", "crewman", "graduate student",
}  # fmt: skip

SYSTEM = """You write role cards for a party game. Everyone but one player is at the same secret place, and each
of them gets a private role there: a kind of person who would really be at that place. Players ask each other
questions about what they wear, the tools or things they use, who they deal with, and a typical problem, and
answer in character, so a role must be concrete enough to answer those questions in a few words.

For the place you are given, write exactly 10 roles:
- title: at most 3 words, plain and everyday (e.g. "night cleaner", "first-time visitor"). The title must not
  contain the place's name, any other name for it, or the name of any place on the game's list. A title like
  "pool attendant" or "ferry captain" is not allowed: it names the place.
- wears: what this person typically has on, in under 12 words.
- does: what they are doing there, in under 15 words.
- deals_with: who or what they mostly interact with, in under 12 words.
- insider_tell: one small detail only a real person in this role would know, in under 20 words.
- generic: true if the role could just as well be at the other places in the same group (for example a visitor,
  a staff member, a regular, a cleaner, a parent with kids); false if it only makes sense at this place.
At least 3 and at most 5 roles must be generic. No two titles may be the same or nearly the same.
Write every word yourself. Do not reuse role names from existing party games. Lowercase titles.
Answer with JSON only."""

ROLE = {
    "type": "object",
    "additionalProperties": False,
    "required": [*FIELDS, "generic"],
    "properties": {**{f: {"type": "string"} for f in FIELDS}, "generic": {"type": "boolean"}},
}
SCHEMA = {
    "name": "roles",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["roles"],
        "properties": {"roles": {"type": "array", "items": ROLE}},
    },
}


def _forms() -> list[str]:
    """Every place name and every other name for one, from the location list and the guess aliases."""
    aliases = guess_aliases()
    return sorted({f.lower() for p in LOCATION_NAMES for f in (p, *LOCATIONS[p], *aliases.get(p, []))}, key=len)


PLACE_RX = [(f, re.compile(r"\b" + re.escape(f).replace(r"\ ", r"[\s-]+") + r"s?\b", re.I)) for f in _forms()]


def place_word(text: str) -> str | None:
    return next((f for f, rx in PLACE_RX if rx.search(text)), None)


def _key(title: str) -> str:
    return re.sub(r"[^a-z]", "", title.lower()).removesuffix("s")


def problems(roles: list[dict]) -> list[str]:
    """Everything wrong with one place's roles, as sentences the model can act on (empty: all good)."""
    out = []
    if len(roles) != ROLES:
        out.append(f"there must be exactly {ROLES} roles, not {len(roles)}")
    seen = {}
    for r in roles:
        t = r["title"].strip()
        if not t or len(t.split()) > MAX_TITLE_WORDS:
            out.append(f'title "{t}" must be 1 to {MAX_TITLE_WORDS} words')
        if w := place_word(t):
            out.append(f'title "{t}" contains a place name ("{w}")')
        if t.lower() in BORROWED_TITLES:
            out.append(f'title "{t}" copies an existing game\'s role name')
        if _key(t) in seen:
            out.append(f'titles "{seen[_key(t)]}" and "{t}" are the same')
        seen[_key(t)] = t
        for f in FIELDS:
            if not r[f].strip():
                out.append(f'"{t}" has an empty {f}')
    generic = sum(r["generic"] for r in roles)
    if generic < MIN_GENERIC:
        out.append(f"only {generic} roles are generic; at least {MIN_GENERIC} must be")
    return out


def clean(r: dict) -> dict:
    return {f: " ".join(r[f].split()) for f in FIELDS} | {"title": " ".join(r["title"].lower().split()),
                                                           "generic": r["generic"]}  # fmt: skip


async def one_place(llm, s, place: str, sem: asyncio.Semaphore, cost: list) -> tuple[str, list[dict], list[str]]:
    others = [p for p in CLUSTERS[CLUSTER_OF[place]] if p != place]
    base = (
        f"The place: {place}.\nThe other places in its group: {', '.join(others)}.\n"
        f"Every place on the game's list (no title may contain any of these): {', '.join(LOCATION_NAMES)}."
    )
    prompt, roles, errs = base, [], ["no answer"]
    async with sem:
        for attempt in range(3):
            raw, usage = "", Usage()
            try:
                async for chunk in llm.stream(
                    model=s.model_for("roles"),
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                    schema=SCHEMA,
                    max_tokens=6000,
                    reasoning_effort=s.override_reasoning_effort,
                    usage=usage,
                ):
                    raw += chunk
                m = s.model_for("roles")
                cost.append(cost_usd(s.prices, m, usage.input_tokens, usage.cached_tokens, usage.output_tokens))
                roles = [clean(r) for r in json.loads(raw)["roles"]]
            except Exception as e:  # noqa: BLE001
                errs = [f"{type(e).__name__}: {e}"]
                continue
            errs = problems(roles)
            print(f"{place}: attempt {attempt + 1}, {len(errs)} problems", file=sys.stderr)
            if not errs:
                break
            prompt = base + "\n\nYour last answer had these problems; fix them all:\n- " + "\n- ".join(errs)
    return place, roles, errs


def write(bank: dict[str, list[dict]], model: str) -> None:
    body = pprint.pformat(bank, width=116, sort_dicts=False)
    OUT.write_text(
        '"""Out of Place role bank: ten roles per place, generated offline by scripts/spy_roles_gen.py '
        f"(model: {model})\nand reviewed by hand. Plain data. `insider_tell` is for review and the consistency "
        'judge only:\nno game prompt may contain it."""\n\n'
        f"ROLES: dict[str, list[dict]] = {body}\n"
    )
    lines = [
        "# Out of Place: role bank",
        "",
        f"Generated by `backend/scripts/spy_roles_gen.py` (model: {model}); the data is "
        "`backend/src/engine/modes/spy_roles.py`. `insider_tell` never goes into a game prompt. "
        "G = generic (fits other places in the same group).",
        "",
        "| Place | Generic | Titles |",
        "|---|---|---|",
    ]
    for place in LOCATION_NAMES:
        rs = bank.get(place, [])
        titles = ", ".join(f"{r['title']}{' (G)' if r['generic'] else ''}" for r in rs)
        lines.append(f"| {place} | {sum(r['generic'] for r in rs)} | {titles} |")
    for cluster, places in CLUSTERS.items():
        lines += ["", f"## {cluster}"]
        for place in places:
            lines += ["", f"### {place}", "", "| Title | G | Wears | Does | Deals with | Insider tell |",
                      "|---|---|---|---|---|---|"]  # fmt: skip
            for r in bank.get(place, []):
                cells = [r["title"], "G" if r["generic"] else "", r["wears"], r["does"], r["deals_with"],
                         r["insider_tell"]]  # fmt: skip
                lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    TABLE.write_text("\n".join(lines) + "\n")


async def main(places: list[str], parallel: int) -> None:
    s = get_settings()
    llm, sem, cost = OpenAILLM(s.openai_api_key), asyncio.Semaphore(parallel), []
    done = await asyncio.gather(*(one_place(llm, s, p, sem, cost) for p in places))
    bank = {}
    if OUT.exists() and set(places) != set(LOCATION_NAMES):  # regenerating some places: keep the rest
        ns: dict = {}
        exec(OUT.read_text(), ns)
        bank = ns["ROLES"]
    failed = {p: e for p, _, e in done if e}
    bank |= {p: r for p, r, e in done if not e}
    bank = {p: bank[p] for p in LOCATION_NAMES if p in bank}
    write(bank, s.model_for("roles"))
    print(f"wrote {OUT} and {TABLE}: {len(bank)} places; cost ${sum(cost):.3f}")
    for p, e in failed.items():
        print(f"FAILED {p}: {e}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--places", nargs="+", default=LOCATION_NAMES, choices=LOCATION_NAMES)
    ap.add_argument("--parallel", type=int, default=8)
    a = ap.parse_args()
    asyncio.run(main(a.places, a.parallel))
