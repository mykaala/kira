import { useEffect, useState } from "react";
import type { SpyConfig } from "./types";

let cached: Promise<SpyConfig> | null = null;

/** Out of Place's title, player range and places list, fetched once per page load. */
export function useSpyConfig(): SpyConfig | null {
  const [config, setConfig] = useState<SpyConfig | null>(null);
  useEffect(() => {
    cached ??= fetch("/api/spy/config").then((r) => {
      if (!r.ok) throw new Error(`config ${r.status}`);
      return r.json();
    });
    cached.then(setConfig).catch(() => {
      cached = null; // try again next time
    });
  }, []);
  return config;
}
