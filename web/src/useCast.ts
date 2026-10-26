import { useEffect, useState } from "react";
import { isCharacterId, type Character, type CharacterId } from "./cast";

export type Cast = Partial<Record<CharacterId, Character>>;

let cached: Promise<Cast> | null = null;

/** The cast as the server describes it (names, voices, quotes, traits), by id. Fetched once per page load. */
export function getCast(): Promise<Cast> {
  cached ??= fetch("/api/cast")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`cast ${r.status}`))))
    .then((list: Character[]) => Object.fromEntries(list.filter((c) => isCharacterId(c.id)).map((c) => [c.id, c])))
    .catch((e) => {
      cached = null; // try again next time
      throw e;
    });
  return cached;
}

export function useCast() {
  const [cast, setCast] = useState<Cast>({});
  useEffect(() => {
    getCast().then(setCast).catch(() => undefined);
  }, []);
  return cast;
}
