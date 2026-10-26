/** Small stroke icons that take the text colour. Decorative: the button around them carries the label. */
const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function InfoIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} {...base}>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 11 V17" />
      <circle cx="12" cy="7.4" r="0.6" fill="currentColor" />
    </svg>
  );
}

export function ArrowIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} {...base}>
      <path d="M4 12 H19 M13 6 L19 12 L13 18" />
    </svg>
  );
}

export function HourglassIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} {...base}>
      <path d="M6 3 H18 M6 21 H18 M7 3 Q7 10 12 12 Q17 14 17 21 M17 3 Q17 10 12 12 Q7 14 7 21" />
    </svg>
  );
}

export function RedrawIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} {...base}>
      <path d="M20 12 A8 8 0 1 1 17.7 6.3 M20 3.5 V8 H15.5" />
    </svg>
  );
}
