import { useEffect, useState } from "react";

// The project was renamed from Berkira: carry saved settings, notes and marks over once.
const OLD_PREFIX = "berkira:";
try {
  for (const key of Object.keys(localStorage)) {
    if (!key.startsWith(OLD_PREFIX)) continue;
    const renamed = `kira:${key.slice(OLD_PREFIX.length)}`;
    if (localStorage.getItem(renamed) === null) localStorage.setItem(renamed, localStorage.getItem(key)!);
    localStorage.removeItem(key);
  }
} catch {
  // storage unavailable; nothing to migrate
}

/** useState that survives a reload. Storage can be unavailable (private windows), so every access is guarded. */
export function usePersisted<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // not saved; the page still works
    }
  }, [key, value]);
  return [value, setValue] as const;
}
