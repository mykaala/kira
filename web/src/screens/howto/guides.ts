/** What each How to Play page says. Rules follow backend/src/engine/modes (mafia.py, and spy_location.py with
 * its default options: 2 votes to survive, a right last-chance guess is a draw). Keep every line short. */
import type { CharacterId } from "../../cast";
import type { QuizSpec } from "./Quiz";
import type { Beat, SceneSpec, Tag, Tone } from "./Scene";

export type Guide = {
  minutes: number;
  goal: string;
  roles: { name: string; tone: Tone; line: string; count?: string }[];
  rolesNote?: string;
  steps: { title: string; line: string }[];
  ends: { who: string; tone: Tone; line: string }[];
  tips: string[];
  sceneTitle: string;
  scene: SceneSpec;
  quiz: QuizSpec;
};

const NAMES: Record<CharacterId, string> = {
  ines: "Ines", bram: "Bram", odile: "Odile", tobiah: "Tobiah",
  kit: "Kit", marguerite: "Marguerite", juno: "Juno", hollis: "Hollis",
};

const FACE_DOWN: Tag = { text: "?", tone: "paper" };
const MAFIA_TAG: Tag = { text: "Mafia", tone: "coral" };

/** One full day: a kill the Doctor misses, an argument, a vote. Six seats deal one Mafia. */
const MAFIA_BEATS: Beat[] = [
  {
    ms: 3200, phase: "Night", caption: "Kit is secretly Mafia, and picks a target.", night: true,
    moods: { kit: "smug" }, tags: { kit: MAFIA_TAG, juno: { text: "Target", tone: "coral" } }, look: "juno",
  },
  {
    ms: 3000, phase: "Night", caption: "The Doctor guards one player. Tonight, the wrong one.", night: true,
    tags: { kit: MAFIA_TAG, juno: { text: "Target", tone: "coral" }, hollis: { text: "Guarded", tone: "teal" } },
  },
  {
    ms: 3000, phase: "Morning", caption: "Juno didn’t wake up. Juno’s card stays face down.",
    moods: { juno: "dead" }, tags: { juno: FACE_DOWN },
  },
  {
    ms: 3400, phase: "Day", caption: "Everyone talks: accuse, defend, bluff.",
    moods: { juno: "dead", bram: "angry" }, tags: { juno: FACE_DOWN },
    say: { who: "bram", text: "It was Kit. Kit barely said a word yesterday." }, look: "kit",
  },
  {
    ms: 3400, phase: "Day", caption: "The Mafia lie like everyone else talks.",
    moods: { juno: "dead", kit: "smug" }, tags: { juno: FACE_DOWN },
    say: { who: "kit", text: "Me? I was asleep. Ask Ines where she was." }, look: "ines",
  },
  {
    ms: 3200, phase: "Day", caption: "Dodging a question is a tell.",
    moods: { juno: "dead" }, tags: { juno: FACE_DOWN },
    say: { who: "ines", text: "Nice dodge, Kit. My vote’s on you." }, look: "kit",
  },
  {
    ms: 3000, phase: "Vote", caption: "Most votes leaves the game.",
    moods: { juno: "dead", kit: "angry" }, tags: { juno: FACE_DOWN }, votes: { kit: 4, ines: 1 }, look: "kit",
  },
  {
    ms: 4200, phase: "The end", caption: "Kit was the only Mafia: the town wins. Every card flips at the results.",
    moods: { juno: "dead", kit: "dead", ines: "smug", bram: "smug" },
    tags: { juno: { text: "Villager", tone: "paper" }, kit: MAFIA_TAG },
  },
];

const PLACE = "Water park";
const CIVILIAN_CARD = { label: "Your card", value: PLACE, tone: "teal" as const };
const SPY_CARD = { label: "Your card", value: "Spy · place unknown", tone: "coral" as const };
const YOU: Tag = { text: "You", tone: "lantern" };

/** The same beat seen from a civilian's seat and from the spy's (Tobiah's). */
function seen(beat: Omit<Beat, "views">, civilian: Partial<Beat> = {}, spy: Partial<Beat> = {}): Beat {
  return {
    ...beat,
    views: {
      civilian: { card: CIVILIAN_CARD, ...civilian },
      spy: { card: SPY_CARD, tags: { tobiah: YOU, ...beat.tags }, ...spy },
    },
  };
}

/** A good answer, the spy narrowing it down, a bad answer, the vote, the last chance. */
const SPY_BEATS: Beat[] = [
  seen({ ms: 3000, phase: "Ask", caption: "Kit asks Bram a question.", say: { who: "kit", text: "Bram, what did you pack for today?" } }),
  seen({ ms: 3200, phase: "Answer", caption: "Bram answers without naming the place.", say: { who: "bram", text: "A towel, sunscreen and way too many snacks." } }),
  seen(
    { ms: 3800, phase: "Think", caption: "" },
    { caption: "Civilians check every answer against the place.", say: { who: "ines", think: true, text: "Towel, sunscreen. Fits a water park." } },
    { caption: "The spy narrows it down, and can name the place the moment they’re sure.", say: { who: "tobiah", think: true, text: "Towel… sunscreen… a pool? A water park? A hot spring?" } },
  ),
  seen({ ms: 3000, phase: "Ask", caption: "Ines asks Tobiah.", say: { who: "ines", text: "Tobiah, what’s the dress code here?" } }),
  seen(
    { ms: 3400, phase: "Answer", caption: "Too vague. Everyone noticed.", say: { who: "tobiah", text: "Uh… smart casual? Whatever’s comfy." }, look: "tobiah" },
    {},
    { caption: "Too vague. The spy didn’t want to guess wrong." },
  ),
  seen({
    ms: 3000, phase: "Vote", caption: "After the last question, everyone votes.",
    moods: { bram: "angry", tobiah: "angry" }, votes: { tobiah: 4, kit: 1 }, look: "tobiah",
  }),
  seen({
    ms: 3400, phase: "Last chance", caption: "Caught! The spy gets one guess at the place.",
    tags: { tobiah: { text: "Spy", tone: "coral" } }, say: { who: "tobiah", text: "Is it… the hot spring?" }, look: "tobiah",
  }),
  seen(
    {
      ms: 4200, phase: "The end", caption: "Wrong place: the civilians win. A right guess would have made it a draw.",
      moods: { tobiah: "dead", ines: "smug", kit: "smug" }, tags: { tobiah: { text: "Spy", tone: "coral" } },
    },
    { card: { label: "The place was", value: PLACE, tone: "lantern" } },
    { card: { label: "The place was", value: PLACE, tone: "lantern" } },
  ),
];

export const GUIDES: Record<string, Guide> = {
  mafia: {
    minutes: 2,
    goal: "Find the killers before they outnumber the town.",
    roles: [
      { name: "Mafia", tone: "coral", count: "1–2", line: "Know each other. Kill one player each night." },
      { name: "Detective", tone: "lavender", line: "Checks one player a night: Mafia or not." },
      { name: "Doctor", tone: "teal", line: "Guards one player a night, never the same one twice in a row." },
      { name: "Villager", tone: "paper", count: "the rest", line: "No powers. Just a voice and a vote." },
    ],
    rolesNote: "Optional, in House rules: the Jester wins by getting voted out; the Bodyguard dies in someone’s place.",
    steps: [
      { title: "Night", line: "The Mafia kill, the Doctor guards, the Detective checks." },
      { title: "Morning", line: "Find out who didn’t wake up." },
      { title: "Talk", line: "Accuse, defend, claim a role, or lie." },
      { title: "Vote", line: "Most votes leaves the game. A tie sends no one." },
    ],
    ends: [
      { who: "The town wins", tone: "teal", line: "when every Mafia member is gone." },
      { who: "The Mafia win", tone: "coral", line: "when they equal or outnumber everyone else." },
    ],
    tips: [
      "Roles stay face down until the results. Even the dead keep their secrets.",
      "Listen for slips: who knows something they shouldn’t?",
      "The AIs remember who accused them. So should you.",
    ],
    sceneTitle: "One night, one day",
    scene: { cast: ["juno", "hollis", "bram", "kit", "ines", "marguerite"], names: NAMES, beats: MAFIA_BEATS },
    quiz: {
      title: "Who slipped?",
      setup: { label: "This morning", value: "Nobody died" },
      question: "The Doctor saved someone in the night. Who knows something only the Mafia could?",
      answers: [
        { who: "ines", name: "Ines", text: "Nobody died? Then the Doctor guessed right.", why: "Fair: a quiet night usually means a save." },
        { who: "bram", name: "Bram", text: "A quiet night. I don’t trust it.", why: "Grumpy, but it gives nothing away." },
        { who: "tobiah", name: "Tobiah", text: "Lucky Ines. I was sure Ines would be gone by now.", right: true, why: "Nobody was told who the target was. Only the Mafia knew it was Ines." },
        { who: "hollis", name: "Hollis", text: "Nothing to go on yet. Let’s hear everyone.", why: "Careful, not suspicious." },
      ],
    },
  },
  "out-of-place": {
    minutes: 2,
    goal: "Everyone knows where you are, except the spy. Catch the spy before they work it out.",
    roles: [
      { name: "Civilian", tone: "teal", count: "the rest", line: "Knows the place. With roles on, also has a job there." },
      { name: "Spy", tone: "coral", count: "1", line: "Doesn’t know the place. Blends in and listens." },
    ],
    rolesNote: "Places come from a list of 40, in groups of four that feel alike.",
    steps: [
      { title: "Ask", line: "Each player still in asks someone one question." },
      { title: "Answer", line: "Convince the civilians. Tell the spy nothing." },
      { title: "Guess", line: "Any time, on anyone’s turn, the spy may name the place. Right wins, wrong loses." },
      { title: "Vote", line: "After the last question, vote. A tie gets one revote." },
    ],
    ends: [
      { who: "Spy caught", tone: "teal", line: "The spy gets one guess at the place. Wrong: civilians win. Right: a draw." },
      { who: "Civilian voted out", tone: "paper", line: "They’re shown to be a civilian, and a new round starts." },
      { who: "The spy wins", tone: "coral", line: "after surviving 2 votes, or when only one civilian is left." },
    ],
    tips: [
      "Too exact and the spy learns the place. Too vague and you look like the spy.",
      "As the spy, give short answers that could fit four places.",
      "As the spy, you don’t have to wait for your turn: name the place as soon as an answer gives it away.",
      "Never say the place, or your role there.",
    ],
    sceneTitle: "Two seats, one answer",
    scene: {
      cast: ["kit", "bram", "ines", "tobiah", "odile"],
      names: NAMES,
      beats: SPY_BEATS,
      views: [{ id: "civilian", label: "As a civilian" }, { id: "spy", label: "As the spy" }],
    },
    quiz: {
      title: "Spot the spy",
      setup: { label: "The place", value: "Ice rink" },
      question: "Everyone answered “What’s the worst part of being here?” Who doesn’t know where they are?",
      answers: [
        { who: "marguerite", name: "Marguerite", text: "Cold feet. Even in two pairs of socks.", why: "Cold feet fits an ice rink." },
        { who: "hollis", name: "Hollis", text: "Falling over in front of strangers.", why: "Falling is a real risk on the ice." },
        { who: "odile", name: "Odile", text: "The waiting. They always run late.", right: true, why: "Waiting fits a dentist or a passport office, not an ice rink." },
        { who: "juno", name: "Juno", text: "The music. Same five songs on a loop.", why: "Rinks really do play the same songs." },
      ],
    },
  },
};
