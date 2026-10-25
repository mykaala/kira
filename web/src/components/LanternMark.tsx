/** The Kira lantern logo mark. */
export function LanternMark({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={(size * 44) / 36} viewBox="0 0 36 44" aria-hidden="true">
      <rect x="12" y="0" width="12" height="5" rx="2" fill="var(--muted)" />
      <path d="M6 8 H30 L27 38 H9 Z" fill="var(--surface-2)" stroke="var(--muted)" strokeWidth="2.5" />
      <path d="M18 14 C24 22 24 28 18 32 C12 28 12 22 18 14 Z" fill="var(--lantern)" />
      <rect x="4" y="38" width="28" height="5" rx="2" fill="var(--muted)" />
    </svg>
  );
}
