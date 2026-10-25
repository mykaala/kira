import { useEffect, useState } from "react";
import type { CharacterId } from "./cast";
import { DEFAULT_LOBBY, newGameRequest, type LobbySettings } from "./game/lobby";
import { usePersisted } from "./persisted";
import { Characters } from "./screens/characters/Characters";
import { PortraitGallery } from "./screens/dev/PortraitGallery";
import { AUTO_KEY, GameScreen } from "./screens/game/GameScreen";
import { Lobby } from "./screens/lobby/Lobby";
import { GameSelect } from "./screens/select/GameSelect";
import { post } from "./useGame";

/** Routes: #/ game select · #/lobby · #/characters · #game=<id> · #/dev/portraits */
const gameFromUrl = () => new URLSearchParams(location.hash.slice(1)).get("game");

export default function App() {
  const [hash, setHash] = useState(location.hash);
  const [lastGame, setLastGame] = usePersisted<string | null>("kira:last-game", null);
  const [lastCast] = usePersisted<CharacterId[]>("kira:last-cast", []);
  const [lobby, setLobby] = usePersisted<LobbySettings>("kira:lobby", DEFAULT_LOBBY);
  const [auto] = usePersisted(AUTO_KEY, true);

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
      onPick={() => go("/lobby")}
      onContinue={(id) => go(`game=${id}`)}
    />
  );
}
