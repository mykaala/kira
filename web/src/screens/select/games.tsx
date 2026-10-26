/** The games on the picker, shared with the How to Play pages (which reuse the card art). */

export type Game = {
  id: string;
  title: string;
  pitch: string;
  chips: string[];
  bluff: number; // out of 3
  cta: string; // the play button; its arrow is an icon
  playable: boolean;
  badge?: string;
  background: string;
  scene: React.ReactNode;
};

export const GAMES: Game[] = [
  {
    id: "mafia",
    title: "Mafia",
    pitch: "Killers hide among the town. Talk by day, survive by night.",
    chips: ["5–9 seats", "~15 min"],
    bluff: 2,
    cta: "Light the lantern",
    playable: true,
    background: "#3A2F5C",
    scene: (
      <>
        <circle cx="310" cy="64" r="30" fill="#F4EBDD" />
        <circle cx="324" cy="56" r="26" fill="#3A2F5C" />
        <circle cx="70" cy="40" r="2" fill="#F4EBDD" />
        <circle cx="140" cy="70" r="1.6" fill="#F4EBDD" />
        <circle cx="220" cy="30" r="2" fill="#F4EBDD" />
        <path d="M0 220 V150 L40 120 L80 150 V220 Z" fill="#1D1830" />
        <path d="M70 220 V130 L120 92 L170 130 V220 Z" fill="#241E3C" />
        <path d="M160 220 V160 H220 V120 L250 100 L280 120 V220 Z" fill="#1D1830" />
        <path d="M270 220 V140 L320 108 L370 140 V220 Z" fill="#241E3C" />
        <path d="M360 220 V160 L400 136 V220 Z" fill="#1D1830" />
        <rect x="108" y="140" width="14" height="18" rx="3" fill="#FFB547" />
        <rect x="242" y="134" width="12" height="16" rx="3" fill="#FFB547" />
        <rect x="308" y="150" width="14" height="18" rx="3" fill="#2A2342" />
        <rect x="30" y="160" width="12" height="16" rx="3" fill="#FFB547" />
      </>
    ),
  },
  {
    id: "secret-hitler",
    title: "Secret Hitler",
    pitch: "Pass policies, read the room, and stop the hidden leader from taking power.",
    chips: ["5–10 seats", "~25 min"],
    bluff: 3,
    cta: "Coming soon",
    playable: false,
    background: "#2E4A54",
    scene: (
      <>
        <path d="M90 100 L200 50 L310 100 Z" fill="#1F3640" />
        <rect x="96" y="100" width="208" height="10" fill="#1F3640" />
        {[112, 152, 232, 272].map((x) => <rect key={x} x={x} y="112" width="16" height="80" fill="#1F3640" />)}
        <rect x="80" y="192" width="240" height="28" fill="#1F3640" />
        <g transform="rotate(-10 180 150)">
          <rect x="150" y="104" width="62" height="86" rx="8" fill="#5CC8B8" stroke="#1D1830" strokeWidth="3" />
          <circle cx="181" cy="147" r="12" fill="none" stroke="#1D1830" strokeWidth="3" />
        </g>
        <g transform="rotate(9 230 150)">
          <rect x="200" y="104" width="62" height="86" rx="8" fill="#FF7A59" stroke="#1D1830" strokeWidth="3" />
          <path d="M218 136 L244 162 M244 136 L218 162" stroke="#1D1830" strokeWidth="3" strokeLinecap="round" />
        </g>
      </>
    ),
  },
  {
    id: "out-of-place",
    title: "", // the server's working title (/api/spy/config): one name, kept in one place
    pitch: "Everyone knows where you are, except the spy. Ask well, answer carefully.",
    chips: ["5–8 seats", "~8 min"],
    bluff: 1,
    cta: "Pick the place",
    playable: true,
    badge: "NEW",
    background: "#5A3550",
    scene: (
      <>
        <rect x="0" y="176" width="400" height="44" fill="#3B2236" />
        <rect x="40" y="110" width="320" height="66" rx="18" fill="#3B2236" />
        {[70, 132, 256].map((x) => <rect key={x} x={x} y="124" width="44" height="28" rx="6" fill="#FFB547" />)}
        <rect x="194" y="124" width="44" height="28" rx="6" fill="#2A2342" />
        <circle cx="100" cy="186" r="12" fill="#1D1830" />
        <circle cx="300" cy="186" r="12" fill="#1D1830" />
        <circle cx="216" cy="138" r="7" fill="#E86FA8" />
        <circle cx="300" cy="62" r="26" fill="none" stroke="#F4EBDD" strokeWidth="6" />
        <path d="M318 80 L340 102" stroke="#F4EBDD" strokeWidth="8" strokeLinecap="round" />
      </>
    ),
  },
];

export const gameById = (id: string) => GAMES.find((g) => g.id === id);
