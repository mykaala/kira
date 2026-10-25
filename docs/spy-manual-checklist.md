# Out of Place: manual browser checklist

Run with the fake model first (`FAKE_LLM=1`), then once with the real model. Start the backend and web app as in
`documentation.md`. Tick each line in a desktop window and again at phone width (devtools, 390 px).

## Picker and lobby
- [ ] The game picker shows Mafia, Secret Hitler (soon) and Out of Place (playable, "NEW"). No console errors.
- [ ] The tab shows the lantern favicon (no 404 for `/favicon.ico` in the network tab) and the title "Kira".
- [ ] Out of Place opens the lobby. The start button stays off until you type a name.
- [ ] Players steps between 5 and 8. Role: Random, Civilian, Spy. "Who plays": choosing exactly players minus one
      characters is required before you can start.
- [ ] Settings survive a reload. Using an AI's name ("Bram") shows an error and doesn't start a game.

## Playing as a civilian (role: Civilian)
- [ ] The top bar shows "The place: …" and whose turn it is; "Your secret" names the place and warns you.
- [ ] AI questions and answers type out on the stage, then join the log. The log follows new lines only when you are
      scrolled to the bottom ("↓ Latest" appears when you scroll up).
- [ ] Chips show Q and A counts and light up whoever is speaking. Click a chip: set a read (Trust/Unsure/Suspect/Spy!)
      and a note; Esc closes it.
- [ ] Your answer turn: the question is shown, the input is focused, the word counter counts to 25, Enter sends.
- [ ] Your ask turn: only legal players are offered (not the person who just asked you, unless nobody else is left).
      You can't send before picking someone.
- [ ] Type the place's name in a question or answer: a warning appears with "Send anyway" and "Edit it".
- [ ] There is no "Call a vote" button anywhere. The vote opens only after every player still in has asked.
- [ ] Vote: pick a portrait; ballots appear one by one; on a tie the revote offers only the tied players.
- [ ] The top bar shows "Round n" and "The spy has survived x of K votes". After a civilian is voted out their chip
      fades with "out · civilian", they're never offered as a target, and round 2 opens with "Round 2 · … asks first."
- [ ] Voted out yourself: the dock says you're watching, your secret still shows the place, Next works with Auto off,
      and "Skip to the end" goes straight to the results.

## Roles (Advanced, on by default)
- [ ] The lobby's Advanced section shows "Roles on"; the roles and angle toggles survive a reload.
- [ ] As a civilian: "Your secret" shows your role card under the place; no other role shows anywhere until the end.
- [ ] Typing your own role title warns "That says your role", with Send anyway and Edit it.
- [ ] Results list every civilian's role at the place on their card. Turning roles off removes the card.

## Playing as the spy (role: Spy)
- [ ] "Your secret" says you're the spy; the places list is on by default, labelled "(the AI spy doesn't get one)",
      and the toggle is remembered.
- [ ] Your ask turn offers "Ask a question" / "Name the place". Clicking a place in the list fills the guess.
      The counter counts to 6 words; "or" or a comma disables sending.
- [ ] Caught by the vote: the last-chance screen asks you to name the place. Right is a draw, wrong a civilian win.

## Results and review
- [ ] Results show the outcome in plain words ("The spy wins!", "The civilians win!", "It's a draw."), the place, who
      the spy was, each round's vote and revote counts and who was voted out (also on their card), any guess with how it was ruled, and each AI's voice on its card.
- [ ] "Replay the whole game" opens the full log; back returns to the results.
- [ ] Play again starts a new game with the same settings; Change settings returns to the lobby; All games goes home.

## Robustness
- [ ] Reload mid-game: the table, log and your turn come back at once (no slow replay).
- [ ] Turn Auto off: AI turns wait for "Next ▸".
- [ ] Stop the backend mid-game: a vote or Next shows an error toast with Retry, and a typed move shows the error
      under the input. Once it's back, retry works (or "That game is gone" appears if the restart lost the game).
- [ ] Keyboard only: Tab reaches every control with a visible focus ring; Enter sends; Space toggles.
- [ ] Mafia still plays from start to finish (smoke test).
