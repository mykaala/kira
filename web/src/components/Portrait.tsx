import type { ReactNode } from "react";
import { CHARACTER_COLOR, type CharacterId } from "../cast";

export type Mood = "neutral" | "angry" | "smug" | "speaking" | "dead";
type EyeRest = "dots" | "lidded" | "closed" | "wink";

/** What stays the same whatever the mood: backdrop, body, head, hair, accessories. Paths are
 * lifted from design/screens; Hollis isn't mocked and is drawn from the spec. */
type Look = {
  behind?: ReactNode; // drawn before the body, e.g. long hair
  shirt: string;
  collar?: ReactNode;
  neck: string;
  neckHeight?: number;
  head: { cy: number; rx: number; ry: number };
  front: ReactNode; // hair, cap, beard: drawn over the head
  eyes: { left: number; right: number; y: number };
  rest: EyeRest; // eye shape when relaxed
  neutralBrows?: string;
  neutralMouth: ReactNode;
  glasses?: (y: number) => ReactNode;
};

const INK = "#1D1830";
const stroke = { stroke: INK, strokeWidth: 3, fill: "none", strokeLinecap: "round" as const };

const LOOKS: Record<CharacterId, Look> = {
  ines: {
    behind: <circle cx="60" cy="28" r="11" fill="#2B1E2F" />,
    shirt: "#1F6F66",
    neck: "#E8B48A",
    head: { cy: 60, rx: 24, ry: 27 },
    front: <path d="M36 58 Q36 32 60 32 Q84 32 84 58 Q74 42 60 42 Q46 42 36 58Z" fill="#2B1E2F" />,
    eyes: { left: 50, right: 70, y: 62 },
    rest: "dots",
    neutralMouth: <path d="M54 76 H66" {...stroke} />,
    glasses: (y) => (
      <g fill="none" stroke={INK} strokeWidth="2.5">
        <circle cx="50" cy={y} r="7" />
        <circle cx="70" cy={y} r="7" />
        <path d={`M57 ${y} H63`} />
      </g>
    ),
  },
  bram: {
    shirt: "#7A2E1E",
    neck: "#F2C9A0",
    head: { cy: 60, rx: 25, ry: 27 },
    front: (
      <>
        <path d="M36 66 Q38 90 60 90 Q82 90 84 66 Q74 80 60 80 Q46 80 36 66Z" fill="#B5542B" />
        <path d="M34 52 Q36 30 60 30 Q84 30 86 52Z" fill="#3B5BA9" />
        <path d="M80 50 L102 54 L82 57Z" fill="#3B5BA9" />
      </>
    ),
    eyes: { left: 51, right: 69, y: 64 },
    rest: "dots",
    neutralBrows: "M44 56 H56 M64 56 H76",
    neutralMouth: <path d="M54 77 H66" {...stroke} />,
  },
  odile: {
    behind: <path d="M30 62 Q30 28 60 28 Q90 28 90 62 L92 112 L28 112Z" fill="#17121F" />,
    shirt: "#4B3F87",
    neck: "#8A5A3B",
    head: { cy: 61, rx: 23, ry: 27 },
    front: <path d="M37 52 Q48 38 66 40 Q80 42 84 56 Q70 46 56 50 Q46 52 37 52Z" fill="#17121F" />,
    eyes: { left: 50, right: 70, y: 64 },
    rest: "lidded",
    neutralMouth: <path d="M56 77 H64" {...stroke} />,
  },
  tobiah: {
    shirt: "#2A2342",
    collar: <path d="M46 92 L60 106 L74 92Z" fill="#F4EBDD" />,
    neck: "#C98B5E",
    neckHeight: 14,
    head: { cy: 60, rx: 25, ry: 28 },
    front: <path d="M34 56 Q38 28 64 30 Q88 32 86 54 Q72 40 48 46 Q40 48 34 56Z" fill="#3A2418" />,
    eyes: { left: 50, right: 70, y: 62 },
    rest: "dots",
    neutralBrows: "M44 54 Q50 50 56 54 M64 52 Q70 46 76 50",
    neutralMouth: <path d="M48 72 Q60 84 72 72" stroke={INK} strokeWidth="3" fill="#F4EBDD" strokeLinecap="round" />,
  },
  kit: {
    shirt: "#1D1830",
    neck: "#F2C9A0",
    neckHeight: 14,
    head: { cy: 61, rx: 24, ry: 27 },
    front: (
      <path d="M34 54 L36 26 L46 40 L54 18 L62 38 L72 20 L76 40 L86 28 L86 54 Q70 42 34 54Z" fill="#2E8B6E" />
    ),
    eyes: { left: 50, right: 70, y: 63 },
    rest: "wink",
    neutralMouth: <path d="M50 74 Q62 82 72 70" {...stroke} />,
  },
  marguerite: {
    shirt: "#4E6B3A",
    neck: "#E8B48A",
    neckHeight: 14,
    head: { cy: 62, rx: 24, ry: 27 },
    front: (
      <g fill="#EFE8F2">
        <circle cx="38" cy="48" r="10" />
        <circle cx="48" cy="36" r="11" />
        <circle cx="62" cy="32" r="11" />
        <circle cx="76" cy="38" r="10" />
        <circle cx="84" cy="50" r="9" />
      </g>
    ),
    eyes: { left: 50, right: 70, y: 64 },
    rest: "closed",
    neutralMouth: <path d="M54 76 Q60 80 66 76" {...stroke} />,
  },
  juno: {
    shirt: "#2F5C9A",
    neck: "#8A5A3B",
    neckHeight: 14,
    head: { cy: 62, rx: 24, ry: 27 },
    front: (
      <>
        <path d="M36 58 Q38 42 60 42 Q82 42 84 58 L84 50 Q60 36 36 50Z" fill="#17121F" />
        <ellipse cx="56" cy="40" rx="30" ry="10" fill="#FF7A59" />
        <circle cx="56" cy="29" r="3" fill="#FF7A59" />
      </>
    ),
    eyes: { left: 51, right: 69, y: 64 },
    rest: "dots",
    neutralMouth: <path d="M53 76 Q60 81 67 76" {...stroke} />,
  },
  hollis: {
    shirt: "#4A3F6E",
    neck: "#D9A47E",
    head: { cy: 61, rx: 24, ry: 27 },
    front: (
      <path
        d="M35 57 Q33 30 60 30 Q87 30 85 57 Q82 45 72 41 Q58 46 42 43 Q37 47 35 57Z"
        fill="#9C97A8"
      />
    ),
    eyes: { left: 50, right: 70, y: 63 },
    rest: "dots",
    neutralBrows: "M44 55 H56 M64 53 Q70 51 76 54",
    neutralMouth: <path d="M54 77 Q61 75 67 78" {...stroke} />,
    glasses: (y) => (
      <g fill="none" stroke={INK} strokeWidth="2.5">
        <rect x="42" y={y - 6} width="16" height="12" rx="2" />
        <rect x="62" y={y - 6} width="16" height="12" rx="2" />
        <path d={`M58 ${y} H62`} />
      </g>
    ),
  },
};

function eye(kind: EyeRest | "x", x: number, y: number, key: string) {
  switch (kind) {
    case "x":
      return <path key={key} d={`M${x - 5} ${y - 3} L${x + 5} ${y + 3} M${x + 5} ${y - 3} L${x - 5} ${y + 3}`} {...stroke} />;
    case "lidded":
      return <path key={key} d={`M${x - 5} ${y} H${x + 5}`} {...stroke} />;
    case "closed":
      return <path key={key} d={`M${x - 5} ${y} Q${x} ${y - 4} ${x + 5} ${y}`} {...stroke} />;
    default:
      return <circle key={key} cx={x} cy={y} r="2.6" fill={INK} />;
  }
}

function eyes(look: Look, mood: Mood) {
  const { left, right, y } = look.eyes;
  if (mood === "dead") return [eye("x", left, y, "l"), eye("x", right, y, "r")];
  let rest = look.rest;
  if (mood === "angry" && (rest === "closed" || rest === "wink")) rest = "dots";
  if (rest === "wink") return [eye("closed", left, y, "l"), eye("dots", right, y, "r")];
  return [eye(rest, left, y, "l"), eye(rest, right, y, "r")];
}

function brows(look: Look, mood: Mood): string | null {
  const { left: l, right: r, y } = look.eyes;
  switch (mood) {
    case "angry":
      return `M${l - 7} ${y - 9} L${l + 5} ${y - 5} M${r + 7} ${y - 9} L${r - 5} ${y - 5}`;
    case "smug":
      return `M${l - 6} ${y - 7} Q${l} ${y - 10} ${l + 6} ${y - 7} M${r - 6} ${y - 12} Q${r} ${y - 19} ${r + 7} ${y - 14}`;
    case "speaking":
      return `M${l - 6} ${y - 8} Q${l} ${y - 12} ${l + 6} ${y - 8} M${r - 6} ${y - 12} Q${r} ${y - 19} ${r + 7} ${y - 14}`;
    case "neutral":
      return look.neutralBrows ?? null;
    default:
      return null;
  }
}

function mouth(look: Look, mood: Mood): ReactNode {
  const y = look.eyes.y + 14;
  switch (mood) {
    case "angry":
      return <path d={`M53 ${y + 1} Q60 ${y - 4} 67 ${y + 1}`} {...stroke} />;
    case "smug":
      return <path d={`M50 ${y - 2} Q62 ${y + 6} 72 ${y - 6}`} {...stroke} />;
    case "speaking":
      return (
        <path
          d={`M50 ${y - 4} Q60 ${y + 6} 70 ${y - 4} Q60 ${y} 50 ${y - 4}Z`}
          fill={INK}
          stroke={INK}
          strokeWidth="2"
          strokeLinejoin="round"
        />
      );
    case "dead":
      return null;
    default:
      return look.neutralMouth;
  }
}

export type PortraitShape = "circle" | "rounded" | "square";

export type PortraitProps = {
  character: CharacterId;
  mood?: Mood;
  /** Pixels, or "fill" to take the container's width (role cards). */
  size?: number | "fill";
  shape?: PortraitShape;
  /** Accessible description, e.g. "Tobiah mid-sentence". Without it the portrait is decorative. */
  label?: string;
  className?: string;
};

const DEAD_BACKDROP = "#8C82A3";

/** A cast member's flat SVG face. Moods change only the brows, eyes and mouth; `dead` also
 * desaturates the portrait. */
export function Portrait({ character, mood = "neutral", size = 56, shape = "circle", label, className }: PortraitProps) {
  const look = LOOKS[character];
  const dead = mood === "dead";
  const fill = size === "fill";
  const px = fill ? 120 : size;
  const radius = shape === "circle" ? "50%" : shape === "rounded" ? `${Math.round(px * 0.16)}px` : 0;
  const browPath = brows(look, mood);

  return (
    <svg
      width={fill ? "100%" : size}
      height={fill ? undefined : size}
      viewBox={fill ? "0 6 120 110" : "0 0 120 120"}
      className={className}
      style={{ borderRadius: radius, flex: "none", display: "block", ...(fill && { height: "auto" }) }}
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
    >
      <rect width="120" height="120" fill={dead ? DEAD_BACKDROP : CHARACTER_COLOR[character]} />
      <g style={dead ? { filter: "grayscale(0.85) brightness(0.92)" } : undefined}>
        {look.behind}
        <path d="M28 120 Q28 92 60 92 Q92 92 92 120Z" fill={look.shirt} />
        {look.collar}
        <rect x="52" y="80" width="16" height={look.neckHeight ?? 16} fill={look.neck} />
        <ellipse cx="60" cy={look.head.cy} rx={look.head.rx} ry={look.head.ry} fill={look.neck} />
        {look.front}
      </g>
      {browPath && <path d={browPath} {...stroke} strokeWidth={mood === "angry" ? 3.5 : 3} />}
      {eyes(look, mood)}
      {look.glasses?.(look.eyes.y)}
      {mouth(look, mood)}
    </svg>
  );
}
