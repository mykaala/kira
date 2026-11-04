import { useEffect, useState } from "react";
import type { CharacterId } from "./cast";
import { DEFAULT_LOBBY, fromSaved, newGameRequest, type LobbySettings } from "./game/lobby";
import { DEFAULT_TUNING, seatTraits, type Tuning } from "./game/tuning";
import { usePersisted } from "./persisted";
import { Characters } from "./screens/characters/Characters";
import { PortraitGallery } from "./screens/dev/PortraitGallery";
import { GameScreen } from "./screens/game/GameScreen";
import { Lobby } from "./screens/lobby/Lobby";
import { HowToPlay } from "./screens/howto/HowToPlay";
import { gameById } from "./screens/select/games";
import { GameSelect } from "./screens/select/GameSelect";
import { SpyGameScreen, SPY_AUTO_KEY } from "./screens/spy/SpyGameScreen";
import { SpyLobby } from "./screens/spy/SpyLobby";
import { DEFAULT_SPY_LOBBY, fromSavedSpy, newSpyGameRequest, type SpyLobbySettings } from "./spy/lobby";
import { useSpyConfig } from "./spy/useSpyConfig";
import { post } from "./useGame";

/** Routes: #/ game select · #/how/<game> · #/lobby · #/characters · #game=<id> · #/dev/portraits
 * · Out of Place: #/spy/lobby · #spy=<id> */
const gameFromUrl = () => new URLSearchParams(location.hash.slice(1)).get("game");
const spyFromUrl = () => new URLSearchParams(location.hash.slice(1)).get("spy");

export default function App() {
  const [hash, setHash] = useState(location.hash);
  const [lastGame, setLastGame] = usePersisted<string | null>("kira:last-game", null);
  const [lastCast] = usePersisted<CharacterId[]>("kira:last-cast", []);
  const [saved, setLobby] = usePersisted<LobbySettings>("kira:lobby", DEFAULT_LOBBY);
  const lobby = fromSaved(saved);
  const [tuning, setTuning] = usePersisted<Tuning>("kira:tuning", DEFAULT_TUNING);
  const [lastSpyGame, setLastSpyGame] = usePersisted<string | null>("kira:last-spy-game", null);
  const [savedSpy, setSpyLobby] = usePersisted<SpyLobbySettings>("kira:spy-lobby", DEFAULT_SPY_LOBBY);
  const spyLobby = fromSavedSpy(savedSpy);
  const [spyAuto] = usePersisted(SPY_AUTO_KEY, true);
  const spyConfig = useSpyConfig();

  useEffect(() => {
    const onHash = () => setHash(location.hash);
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [hash]);
  useEffect(() => {
    // once: an old random table becomes a drawn one, and stays
    if ("chooseCast" in saved) setLobby(lobby);
    if ("chooseCast" in savedSpy || savedSpy.cast.length !== savedSpy.players - 1) setSpyLobby(spyLobby);
  }, []);

  const go = (to: string) => {
    location.hash = to;
  };
  const start = async () => {
    const t = { ...DEFAULT_TUNING, ...tuning };
    const { game_id } = await post("/api/games", newGameRequest(lobby, false, t.difficulty, await seatTraits(lobby.cast, t)));
    setLastGame(game_id);
    go(`game=${game_id}`);
  };

  const startSpy = async () => {
    const { game_id } = await post("/api/spy/games", newSpyGameRequest(spyLobby, spyAuto));
    setLastSpyGame(game_id);
    go(`spy=${game_id}`);
  };

  const spyId = spyFromUrl();
  if (spyId) {
    return (
      <SpyGameScreen
        key={spyId}
        gameId={spyId}
        onExit={() => {
          setLastSpyGame(null);
          go("/");
        }}
        onRematch={() => startSpy().catch(() => go("/spy/lobby"))}
        onSettings={() => {
          setLastSpyGame(null);
          go("/spy/lobby");
        }}
      />
    );
  }
  if (hash.startsWith("#/spy/lobby")) {
    return (
      <SpyLobby title={spyConfig?.title ?? "…"} settings={spyLobby} onChange={setSpyLobby}
                onStart={startSpy} />
    );
  }

  const gameId = gameFromUrl();
  if (gameId) {
    return (
      <GameScreen
        key={gameId}
        gameId={gameId}
        onExit={() => {
          setLastGame(null);
          go("/");
        }}
        onRematch={() => start().catch(() => go("/lobby"))}
      />
    );
  }
  const pickGame = (game: string) => go(game === "out-of-place" ? "/spy/lobby" : "/lobby");
  const howTo = hash.match(/^#\/how\/([\w-]+)/)?.[1];
  if (howTo && gameById(howTo)) return <HowToPlay key={howTo} gameId={howTo} onPlay={pickGame} />;
  if (hash.startsWith("#/dev/portraits")) return <PortraitGallery />;
  if (hash.startsWith("#/characters")) return <Characters tuning={{ ...DEFAULT_TUNING, ...tuning }} onChange={setTuning} />;
  if (hash.startsWith("#/lobby")) {
    return <Lobby settings={lobby} difficulty={{ ...DEFAULT_TUNING, ...tuning }.difficulty} onChange={setLobby} onStart={start} />;
  }
  return (
    <GameSelect
      lastGame={lastGame}
      lastCast={lastCast}
      onPick={pickGame}
      onContinue={(id) => go(`game=${id}`)}
      lastSpyGame={lastSpyGame}
      onContinueSpy={(id) => go(`spy=${id}`)}
    />
  );
}
