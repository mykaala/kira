from bots import play_random
from server.metrics import aggregate_metrics, game_metrics, parse_transcript, phrase_uses, record_of, text_claims
from server.runsummary import transcript

TRANSCRIPT = [
    "=== Day 1: night ===",
    "  · [private:p2] Your investigation: Wren is MAFIA.",
    "  · [private:p0] You protected Mei tonight.",
    "=== Day 1: morning ===",
    "  · No one died.",
    "=== Day 1: discussion ===",
    "  Sasha (villager): no death, doctor hit or mafia stalled",
    "  Dara (detective): rafi is mafia. i'm detective. vote him",
    "  Wren (mafia): dara's claim is convenient. so convenient",
    "  Rafi (mafia): im the real detective, i checked dara and she's mafia",
    "  Wren (mafia): convenient again lol",
    "=== Day 1: vote ===",
    "  · Wren voted for Dara.",
    "  · Rafi voted for Dara.",
    "  · Dara voted for Rafi.",
    "  · Rafi was eliminated. They were a mafia.",
    "=== Day 2: night ===",
    "  · [channel:mafia] The mafia chose Mei.",
    "  · [private:p0] You protected Mei tonight.",
    "=== Day 2: morning ===",
    "  · No one died.",
    "  · The village wins! Mei was doctor, Rafi was mafia, Dara was detective, Wren was mafia, Sasha was villager.",
]
SUMMARY = {"winner": "village", "days": 2, "transcript": TRANSCRIPT}


def test_transcript_parses_back_into_roles_and_events():
    rec = parse_transcript(SUMMARY)
    assert rec["roles"] == {"Sasha": "villager", "Dara": "detective", "Wren": "mafia", "Rafi": "mafia", "Mei": "doctor"}
    kinds = [e["kind"] for e in rec["events"] if e["kind"] != "phase"]
    assert kinds.count("vote") == 3 and kinds.count("mafia_choice") == 1 and kinds.count("morning") == 2
    elim = next(e for e in rec["events"] if e["kind"] == "elimination")
    assert elim["target"] == "Rafi" and elim["day"] == 1


def test_text_claims_find_target_and_result():
    claims = text_claims(parse_transcript(SUMMARY))
    assert [(c["actor"], c["target"], c["result"], c["true"]) for c in claims] == [
        ("Dara", "Rafi", "mafia", True),
        ("Rafi", "Dara", "mafia", False),
    ]


def test_game_metrics():
    m = game_metrics(parse_transcript(SUMMARY))
    assert m["first_check"] == "hit"
    assert m["day1_claim"]["true"] and m["day1_claim"]["target"] == "Rafi"
    assert m["mafia_counterclaim"] and m["mafia_fake_claim"]
    assert m["first_mafia_caught"] == {"day": 1, "how": "after a detective claim"}
    assert (m["kills_attempted"], m["kills_blocked_by_doctor"], m["doctor_repeat_saves"]) == (1, 1, 1)
    assert m["day1_death_talk"]
    assert (m["mafia_votes_together"], m["mafia_votes_split"]) == (1, 0)
    assert m["voice"]["phrase_uses"] == {"convenient": 3}
    assert m["voice"]["repeated_phrase_uses"] == 2  # Wren used it three times


def test_aggregate_counts_check_hits_against_wins():
    a = aggregate_metrics([game_metrics(parse_transcript(SUMMARY))] * 2)
    assert a["first_check"] == {"hit": 2, "hit_village_wins": 2, "miss_or_none": 0, "miss_village_wins": 0}
    assert a["kills"]["blocked_rate"] == 1.0
    assert a["day1_claim"] == {"games_with_claim": 2, "true": 2, "fake": 0}


def test_phrases_match_inflections_but_not_tell_me():
    assert phrase_uses("tell me why, that's a tell, so staged and easier") == ["staged", "tell", "easy"]
    assert phrase_uses("piling on kofi, pile-on again") == ["pile-on", "pile-on"]


def test_live_record_and_parsed_transcript_agree():
    for seed in range(20):
        state = play_random(seed)
        live = game_metrics(record_of(state))
        parsed = game_metrics(
            parse_transcript({"winner": state.winner, "days": state.day, "transcript": transcript(state)})
        )
        # (claims are left out: live records carry the structured claims, transcripts only text)
        for key in (
            "first_check",
            "kills_attempted",
            "kills_blocked_by_doctor",
            "doctor_repeat_saves",
            "mafia_votes_together",
            "mafia_votes_split",
        ):
            assert live[key] == parsed[key], (seed, key)
