import pytest

from agents.checks import roles_claimed, unsupported_references

PLAYERS = ["Rafi", "Juno", "Toby", "Mei", "Dara", "Kofi", "Sasha"]  # any names work; the check is name-agnostic


def check(text, said=None, claimed=None, speaker="Rafi"):
    """`said`: what each player has posted this game (players not listed have said nothing)."""
    said = {n: (said or {}).get(n, []) for n in PLAYERS}
    return [name for name, _ in unsupported_references(text, speaker, said, claimed or {})]


@pytest.mark.parametrize(
    "text, said, flagged",
    [
        ("Dara's claim doesn't add up.", {}, ["Dara"]),
        ("Dara’s story about the doctor feels thin.", {}, ["Dara"]),
        ("Mei said she trusts Toby, which is odd.", {}, ["Mei"]),
        ("Kofi, your defense was weak.", {}, ["Kofi"]),
        # they have spoken, but never claimed the role they're said to have claimed
        ("Toby, you said you were the doctor. Prove it.", {"Toby": ["hi all"]}, ["Toby"]),
        ("Juno already claimed villager and I don't buy it.", {"Juno": ["kofi is sus"]}, ["Juno"]),
        ("dara's detective claim is fake", {"Dara": ["kofi is sus"]}, ["Dara"]),
        ("ok so mei, you claimed cop", {"Mei": ["lol"]}, ["Mei"]),
    ],
)
def test_flags_statements_nobody_made(text, said, flagged):
    assert check(text, said) == flagged


@pytest.mark.parametrize(
    "text, said, claimed",
    [
        ("Dara has been quiet. Why?", {}, {}),
        ("Nobody has said anything yet, so let's start somewhere.", {}, {}),
        ("Mei said she trusts Toby, which is odd.", {"Mei": ["i trust toby"]}, {}),
        ("I said I'm a villager and I stand by it.", {}, {}),
        ("Rafi's claim stands: I'm a villager.", {}, {}),  # the speaker's own claim
        ("Sasha, what do you think about Kofi?", {}, {}),
        # a claim from an earlier day is fine without saying "yesterday"
        ("sasha still bugs me, but juno's detective claim checks out", {"Juno": ["im detective. mei is mafia"]}, {}),
        # the claims log counts even if the words were different
        ("dara's detective claim is fake", {"Dara": ["wren is mafia, trust me"]}, {"Dara": {"detective"}}),
        # the false positives from the 20-game baseline
        ("nah toby, your doctor claim doesn't erase my wren check", {"Toby": ["im the doc, relax"]}, {}),
        ("kofi, you keep calling it heat while dodging why your rafi read was off", {"Kofi": ["heat on me lol"]}, {}),
        ("toby, rafi flipping mafia makes your mei theory look like panic, not proof", {"Toby": ["mei did it"]}, {}),
        ("toby's zero reads was still a dodge", {"Toby": ["no reads yet"]}, {}),
    ],
)
def test_does_not_flag_supported_or_neutral_messages(text, said, claimed):
    assert check(text, said, claimed) == []


def test_roles_claimed_from_own_words():
    assert roles_claimed(["im the doc lol", "cop here", "kofi is a villager"]) == {"doctor", "detective"}


def test_reason_names_what_was_wrong():
    said = {n: [] for n in PLAYERS} | {"Toby": ["hey"]}
    [(_, why)] = unsupported_references("toby, your detective claim is fake", "Rafi", said, {})
    assert why == "says Toby claimed detective, but they never did"


@pytest.mark.parametrize(
    "message, role",
    [
        ("Nobody’s spoken yet, so: I’m the detective, and I investigated Rafi last night.", "detective"),
        ("kofi is mafia. i checked him last night", "detective"),
        ("I’m claiming plain villager, and silence isn't innocence.", "villager"),
        ("Rafi, I’m plain villager, and I’m absolutely not mafia.", "villager"),
    ],
)
def test_roles_claimed_handles_curly_quotes_and_results(message, role):
    assert role in roles_claimed([message])


# Planted bad messages. Juno and Kit never spoke; Bram, Odile, Hollis and Tobiah spoke but never claimed a
# role; Ines claimed detective (in the claims log), not doctor.
PLANT_SAID = {
    "Ines": ["i'm detective, bram is mafia"],
    "Bram": ["odile is sus"],
    "Odile": ["bram talks too much"],
    "Juno": [],
    "Kit": [],
    "Hollis": ["hi"],
    "Tobiah": ["lol"],
    "Marguerite": [],
}


@pytest.mark.parametrize(
    "text, who",
    [
        ("juno said she trusts kit", "Juno"),
        ("juno's story makes no sense", "Juno"),
        ("Juno’s story makes no sense", "Juno"),
        ("kit, you said odile was clear", "Kit"),
        ("kit, your defense was weak", "Kit"),
        ("nah kit, your argument is lazy", "Kit"),
        ("kit claimed bram was lying", "Kit"),
        ("Kit’s accusation came out of nowhere", "Kit"),
        ("bram claimed detective earlier", "Bram"),
        ("bram's detective claim is fake", "Bram"),
        ("Bram’s detective claim is fake", "Bram"),
        ("odile said she's the doctor", "Odile"),
        ("odile said she’s the doctor", "Odile"),
        ("odile, you claimed doctor", "Odile"),
        ("odile, your doctor claim is weak", "Odile"),
        ("ok so bram, you said you were the cop", "Bram"),
        ("bram already claimed villager lol", "Bram"),
        ("odile claims to be the bodyguard", "Odile"),
        ("hollis, you said you’re the detective", "Hollis"),
        ("tobiah's doctor claim doesn't add up", "Tobiah"),
        ("bram said hes the doc", "Bram"),
        ("ines's doctor claim is weird", "Ines"),
        # phrasings the first version missed
        ("according to juno, kit is clean", "Juno"),
        ("juno told us she was town", "Juno"),
        ("remember when kit called me mafia", "Kit"),
        ("bram swears he's the detective", "Bram"),
        ("odile insisted she was the doctor", "Odile"),
        ("as kit put it, bram is the problem", "Kit"),
        ("kit literally said vote odile", "Kit"),
        ("juno's whole trust me thing is weird", "Juno"),
        ("bram outed himself as detective", "Bram"),
        ("odile is claiming doc now?", "Odile"),
    ],
)
def test_planted_misattributions_are_caught(text, who):
    flagged = unsupported_references(text, "Marguerite", PLANT_SAID, {"Ines": {"detective"}})
    assert who in [name for name, _ in flagged]


@pytest.mark.parametrize(
    "text, said, flagged",
    [
        ("marg's detective claim is fake", {"Marguerite": ["lol"]}, ["Marguerite"]),  # short name, never claimed
        ("marg's detective claim is fake", {"Marguerite": ["i'm the detective"]}, []),
        ("tobi said kit is clean", {}, ["Tobiah"]),  # "tob" alone would also match Toby
    ],
)
def test_short_names_are_checked(text, said, flagged):
    players = PLAYERS + ["Marguerite", "Tobiah"]
    full = {n: (said or {}).get(n, []) for n in players}
    assert [n for n, _ in unsupported_references(text, "Rafi", full, {})] == flagged


def test_names_accepts_short_forms_only_as_whole_words():
    from agents.checks import names

    assert names("marg is lying", "Marguerite") and names("ok TOB", "Tobiah")
    assert not names("margarine", "Marguerite") and not names("ma is lying", "Marguerite")


# Planted nicknames and short names. Same table as PLANT_SAID plus the cast's real nicknames.
NICK_SAID = {
    "Ines": ["i'm detective, bram is mafia"],
    "Bram": ["odile is sus"],
    "Odile": ["bram talks too much"],
    "Juno": [],
    "Kit": [],
    "Hollis": ["hi"],
    "Tobiah": ["lol"],
    "Marguerite": ["slow down"],
}


@pytest.mark.parametrize(
    "text, who",
    [
        ("marg said she's the doctor", "Marguerite"),  # nickname, spoke but never claimed
        ("Marg’s doctor claim is weak", "Marguerite"),  # nickname, curly apostrophe
        ("maggie, you claimed cop", "Marguerite"),  # second nickname, addressed
        ("toby's detective claim is fake", "Tobiah"),  # nickname that isn't a prefix
        ("toby, you said you were the doctor", "Tobiah"),
        ("tobi claimed villager earlier", "Tobiah"),  # short form
        ("holl's bodyguard claim makes no sense", "Hollis"),  # short form
        ("odi said she's the detective", "Odile"),
        ("according to jun, kit is clean", "Juno"),  # short form of someone who never spoke
        ("as kit put it, bram is lying", "Kit"),  # full short name, never spoke
    ],
)
def test_planted_nicknames_and_short_names_are_caught(text, who):
    flagged = unsupported_references(text, "Ines", NICK_SAID, {"Ines": {"detective"}})
    assert who in [name for name, _ in flagged]


@pytest.mark.parametrize(
    "text",
    [
        "marg is lying, look at her votes",  # names someone, attributes nothing
        "toby voted last again",
        "the margin on that vote was one",  # "margin" is not marg
        "hold on, why kit",  # "hold" is not Hollis
        "ines's detective claim still stands",  # Ines really claimed it
    ],
)
def test_nicknames_and_lookalikes_do_not_false_flag(text):
    assert unsupported_references(text, "Bram", NICK_SAID, {"Ines": {"detective"}}) == []
