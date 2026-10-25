import { useEffect, useState } from "react";
import type { CharacterId } from "./cast";
import { DEFAULT_LOBBY, newGameRequest, type LobbySettings } from "./game/lobby";
import { usePersisted } from "./persisted";
import { Characters } from "./screens/characters/Characters";
import { PortraitGallery } from "./screens/dev/PortraitGallery";
import { AUTO_KEY, GameScreen } from "./screens/game/GameScreen";
import { Lobby } from "./screens/lobby/Lobby";
import { GameSelect } from "./screens/select/GameSelect";
import { SpyGameScreen, SPY_AUTO_KEY } from "./screens/spy/SpyGameScreen";
import { SpyLobby } from "./screens/spy/SpyLobby";
import { DEFAULT_SPY_LOBBY, newSpyGameRequest, type SpyLobbySettings } from "./spy/lobby";
import { useSpyConfig } from "./spy/useSpyConfig";
import { post } from "./useGame";

/** Routes: #/ game select · #/lobby · #/characters · #game=<id> · #/dev/portraits
 * · Out of Place: #/spy/lobby · #spy=<id> */
const gameFromUrl = () => new URLSearchParams(location.hash.slice(1)).get("game");
const spyFromUrl = () => new URLSearchParams(location.hash.slice(1)).get("spy");

export default function App() {
  const [hash, setHash] = useState(location.hash);
  const [lastGame, setLastGame] = usePersisted<string | null>("kira:last-game", null);
  const [lastCast] = usePersisted<CharacterId[]>("kira:last-cast", []);
  const [lobby, setLobby] = usePersisted<LobbySettings>("kira:lobby", DEFAULT_LOBBY);
  const [auto] = usePersisted(AUTO_KEY, true);
  const [lastSpyGame, setLastSpyGame] = usePersisted<string | null>("kira:last-spy-game", null);
  const [spyLobby, setSpyLobby] = usePersisted<SpyLobbySettings>("kira:spy-lobby", DEFAULT_SPY_LOBBY);
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

  const go = (to: string) => {
    location.hash = to;
  };
  const start = async () => {
    const { game_id } = await post("/api/games", newGameRequest({ ...DEFAULT_LOBBY, ...lobby }, auto));
    setLastGame(game_id);
    go(`game=${game_id}`);
  };

  const startSpy = async () => {
    const { game_id } = await post("/api/spy/games", newSpyGameRequest({ ...DEFAULT_SPY_LOBBY, ...spyLobby }, spyAuto));
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
      <SpyLobby title={spyConfig?.title ?? "…"} settings={{ ...DEFAULT_SPY_LOBBY, ...spyLobby }} onChange={setSpyLobby}
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
  if (hash.startsWith("#/dev/portraits")) return <PortraitGallery />;
  if (hash.startsWith("#/characters")) return <Characters />;
  if (hash.startsWith("#/lobby")) {
    return <Lobby settings={{ ...DEFAULT_LOBBY, ...lobby }} onChange={setLobby} onStart={start} />;
  }
  return (
    <GameSelect
      lastGame={lastGame}
      lastCast={lastCast}
      onPick={(game) => go(game === "out-of-place" ? "/spy/lobby" : "/lobby")}
      onContinue={(id) => go(`game=${id}`)}
      lastSpyGame={lastSpyGame}
      onContinueSpy={(id) => go(`spy=${id}`)}
    />
  );
}
