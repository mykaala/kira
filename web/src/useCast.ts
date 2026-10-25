import { useEffect, useState } from "react";
import { isCharacterId, type Character, type CharacterId } from "./cast";

/** The cast as the server describes it (names, voices, quotes, traits), by id. */
export function useCast() {
  const [cast, setCast] = useState<Partial<Record<CharacterId, Character>>>({});
  useEffect(() => {
    fetch("/api/cast")
      .then((r) => (r.ok ? r.json() : []))
      .then((list: Character[]) =>
        setCast(Object.fromEntries(list.filter((c) => isCharacterId(c.id)).map((c) => [c.id, c]))),
      )
      .catch(() => undefined);
  }, []);
  return cast;
}
