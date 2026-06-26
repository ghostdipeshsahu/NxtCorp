// HRM-inspired 2D character avatars. Bigger eyes, clear silhouettes,
// warm palette. One SVG per (character, expression, avatarId).

const CHARACTERS = {
  priya: {
    label: 'Priya Sharma',
    role: 'Manager',
    skin: '#c8845a',
    hair: '#1a0f0a',
    accent: '#2a3545',     // blazer
    accent2: '#3d4a5e',    // collar
    hairStyle: 'priya_bun',
    glasses: true,
  },
  arjun: {
    label: 'Arjun Mehta',
    role: 'Senior Developer',
    skin: '#b8724a',
    hair: '#0f0806',
    accent: '#1e3a2e',
    accent2: '#264b3a',
    hairStyle: 'arjun_messy',
    stubble: true,
  },
  zara: {
    label: 'Zara Khan',
    role: 'QA Engineer',
    skin: '#c07850',
    hair: '#0a0608',
    accent: '#2d2040',
    accent2: '#3a2a50',
    hairStyle: 'zara_long',
  },
  ravi: {
    label: 'Ravi Sir',
    role: 'CTO',
    skin: '#a86840',
    hair: '#3d3530',      // salt-and-pepper
    accent: '#1a2535',
    accent2: '#26344a',
    hairStyle: 'ravi_distinguished',
    glasses: false,
  },
  player: {
    label: 'You',
    role: 'AI Trainee',
    // merged with PLAYER_AVATARS[avatarId] at render time
  },
  // v4 — Meeting Room cast. These appear only inside the briefing scene;
  // none of them route through chat, coffee, cabin, or coaching paths.
  rahul: {
    label: 'Rahul Mehta',
    role: 'HR Manager',
    skin: '#b67a52',
    hair: '#3a302a',       // salt-and-pepper at temples
    accent: '#3d5a72',     // formal blue button-down
    accent2: '#4d6a82',
    hairStyle: 'ravi_distinguished',  // mid-40s, dignified
    glasses: true,
  },
  sneha: {
    label: 'Sneha Kapoor',
    role: 'Finance Manager',
    skin: '#d49474',
    hair: '#1a0f0a',
    accent: '#5a3d6a',     // plum blazer
    accent2: '#6a4d7a',
    hairStyle: 'bun_updo',  // sharp + precise
  },
  vikram: {
    label: 'Vikram Nair',
    role: 'Product Manager',
    skin: '#a96b40',
    hair: '#0f0806',
    accent: '#2d6a4f',     // teal shirt — casual professional
    accent2: '#3d7a5f',
    hairStyle: 'medium',    // early-30s, casual
  },
  ananya: {
    label: 'Ananya Singh',
    role: 'Client Representative',
    skin: '#c8845a',
    hair: '#15100b',
    accent: '#2c2c2c',     // formal business charcoal
    accent2: '#3d3d3d',
    hairStyle: 'long_open',  // late-30s, formal
  },
};

export const PLAYER_AVATARS = {
  avatar_01: { skin: '#d49474', hair: '#1f1208', accent: '#8b5a3c', hairStyle: 'short', name: 'Avatar 1' },
  avatar_02: { skin: '#c8845a', hair: '#241510', accent: '#3f6a8c', hairStyle: 'medium', name: 'Avatar 2' },
  // Female avatars — same warm skin tones as Avatar 1 / Avatar 2 so the
  // face stays visible. Only the hair + shirt accent differs.
  avatar_03: { skin: '#d49474', hair: '#1f1208', accent: '#2d6a4f', hairStyle: 'long_open', name: 'Avatar 3' },
  avatar_04: { skin: '#c8845a', hair: '#241510', accent: '#a23b72', hairStyle: 'bun_updo',  name: 'Avatar 4' },
  avatar_05: { skin: '#dca888', hair: '#5d3a1a', accent: '#7b3dc7', hairStyle: 'glasses',    name: 'Avatar 5' },
};
export const PLAYER_AVATAR_IDS = Object.keys(PLAYER_AVATARS);

// Per-expression eye + mouth + brow geometry. Big bold features.
const EXPRESSIONS = {
  happy:     { mouth: 'M21 36 Q28 42 35 36',     brow: 'M19 19 L25 17 M31 17 L37 19', eye: 'open',     blush: true },
  excited:   { mouth: 'M20 34 Q28 44 36 34 Z',   brow: 'M18 18 L25 16 M31 16 L38 18', eye: 'sparkle',  blush: true },
  thinking:  { mouth: 'M24 38 L32 38',           brow: 'M19 21 L25 22 M31 18 L37 21', eye: 'narrow',   blush: false },
  concerned: { mouth: 'M21 39 Q28 35 35 39',     brow: 'M19 17 L25 21 M31 21 L37 17', eye: 'open',     blush: false },
  proud:     { mouth: 'M22 36 Q28 38 34 36',     brow: 'M19 18 L25 17 M31 17 L37 18', eye: 'open',     blush: false },
  neutral:   { mouth: 'M23 37 L33 37',           brow: 'M19 19 L25 19 M31 19 L37 19', eye: 'open',     blush: false },
};

function Eyes({ shape }) {
  // Larger eyes than before — HRM/Pixar style readable from distance.
  if (shape === 'narrow') {
    return (
      <g stroke="#1f1208" strokeWidth="2" strokeLinecap="round" fill="none">
        <path d="M21 26 L26 26" />
        <path d="M30 26 L35 26" />
      </g>
    );
  }
  if (shape === 'sparkle') {
    return (
      <g>
        <ellipse cx="23.5" cy="26" rx="2.6" ry="2.8" fill="#1f1208" />
        <ellipse cx="32.5" cy="26" rx="2.6" ry="2.8" fill="#1f1208" />
        <circle cx="22.5" cy="25" r="0.9" fill="#fff5e4" />
        <circle cx="31.5" cy="25" r="0.9" fill="#fff5e4" />
        <circle cx="24.4" cy="27" r="0.4" fill="#fff5e4" />
        <circle cx="33.4" cy="27" r="0.4" fill="#fff5e4" />
      </g>
    );
  }
  return (
    <g>
      <ellipse cx="23.5" cy="26" rx="2.3" ry="2.5" fill="#1f1208" />
      <ellipse cx="32.5" cy="26" rx="2.3" ry="2.5" fill="#1f1208" />
      <circle cx="22.7" cy="25.2" r="0.75" fill="#fff5e4" />
      <circle cx="31.7" cy="25.2" r="0.75" fill="#fff5e4" />
    </g>
  );
}

function Glasses() {
  return (
    <g stroke="#2a2218" strokeWidth="1.2" fill="none">
      <rect x="19" y="22.5" width="9" height="7" rx="1.8" />
      <rect x="28" y="22.5" width="9" height="7" rx="1.8" />
      <line x1="27.5" y1="25.5" x2="28.5" y2="25.5" />
    </g>
  );
}

function Stubble() {
  return (
    <g fill="#0f0806" opacity="0.55">
      <circle cx="22" cy="40" r="0.4" />
      <circle cx="25" cy="41" r="0.4" />
      <circle cx="28" cy="41.5" r="0.4" />
      <circle cx="31" cy="41" r="0.4" />
      <circle cx="34" cy="40" r="0.4" />
      <circle cx="23.5" cy="42" r="0.35" />
      <circle cx="29" cy="43" r="0.35" />
      <circle cx="32.5" cy="42" r="0.35" />
    </g>
  );
}

function Blush() {
  return (
    <g fill="#e89270" opacity="0.55">
      <ellipse cx="18" cy="32" rx="2.4" ry="1.4" />
      <ellipse cx="38" cy="32" rx="2.4" ry="1.4" />
    </g>
  );
}

function Hair({ style, color }) {
  switch (style) {
    case 'priya_bun':
      // Priya: long hair pulled back into a tidy high bun. CRITICAL: the
      // face oval stays fully visible — hair arcs over the crown and
      // drops as side curtains, never overlaying the forehead, eyes,
      // cheeks, or glasses underneath.
      return (
        <g>
          {/* Long hair: top crown + side curtains down to the shoulders */}
          <path
            d="M11 16 Q11 7 28 6 Q45 7 45 16 L45 50 Q42 41 39 35 L39 16 Q28 13 17 16 L17 35 Q14 41 11 50 Z"
            fill={color}
          />
          {/* High bun on top of head */}
          <ellipse cx="28" cy="6" rx="5.5" ry="3.8" fill={color} />
          <ellipse cx="28" cy="5" rx="3.8" ry="2.4" fill="#000" opacity="0.18" />
          {/* Small gold stud earrings */}
          <circle cx="13.5" cy="32" r="1" fill="#d4af37" />
          <circle cx="42.5" cy="32" r="1" fill="#d4af37" />
        </g>
      );
    case 'arjun_messy':
      // Slightly messy / spiked top.
      return (
        <g>
          <path
            d="M14 24 Q14 10 28 10 Q42 10 42 24 L42 21 Q40 15 36 14 L34 17 L31 13 L28 16 L25 13 L22 17 L20 14 Q16 15 14 21 Z"
            fill={color}
          />
        </g>
      );
    case 'zara_long':
      // Zara: sleek straight hair past shoulders. CRITICAL: face oval
      // stays fully visible — hair arcs over the crown and drops as side
      // curtains, with the forehead, eyes, cheeks, and mouth left clear.
      return (
        <g>
          <path
            d="M11 16 Q11 7 28 6 Q45 7 45 16 L45 50 Q42 41 39 35 L39 16 Q28 13 17 16 L17 35 Q14 41 11 50 Z"
            fill={color}
          />
          {/* Subtle center-part shadow on the crown above the hairline */}
          <path d="M28 7 L28 13" stroke="#000" strokeWidth="0.5" opacity="0.3" fill="none" />
        </g>
      );
    case 'ravi_distinguished':
      // Receding hairline with salt-and-pepper temples.
      return (
        <g>
          <path d="M15 19 Q18 14 28 13 Q38 14 41 19 Q34 16 28 16 Q22 16 15 19 Z" fill={color} />
          <ellipse cx="16" cy="22" rx="2.6" ry="1.4" fill="#7a6f63" opacity="0.7" />
          <ellipse cx="40" cy="22" rx="2.6" ry="1.4" fill="#7a6f63" opacity="0.7" />
        </g>
      );
    case 'short':
      return <path d="M15 22 Q16 11 28 10 Q40 11 41 22 Q34 16 28 16 Q22 16 15 22 Z" fill={color} />;
    case 'medium':
      return <path d="M14 24 Q14 10 28 10 Q42 10 42 24 L42 30 Q38 20 28 20 Q18 20 14 30 Z" fill={color} />;
    case 'bald_beard':
      return (
        <g>
          <ellipse cx="28" cy="13" rx="13" ry="2" fill={color} opacity="0.35" />
          <path d="M16 36 Q20 44 28 44 Q36 44 40 36 Q35 42 28 42 Q21 42 16 36 Z" fill={color} />
        </g>
      );
    case 'headscarf':
      return (
        <path
          d="M12 28 Q12 6 28 6 Q44 6 44 28 L44 44 L40 44 Q38 30 28 30 Q18 30 16 44 L12 44 Z"
          fill={color}
        />
      );
    case 'glasses':
      // (Player variant 5 — keep the glasses primitive on top of regular hair)
      return (
        <g>
          <path d="M15 21 Q16 11 28 10 Q40 11 41 21 Q34 15 28 15 Q22 15 15 21 Z" fill={color} />
          <Glasses />
        </g>
      );
    case 'long_open':
      // Female avatar — long straight hair past the shoulders.
      // CRITICAL: face oval stays fully visible. The hair path arcs over
      // the top of the head, drops down as two side "curtains" past the
      // shoulder line, and cuts a clear forehead window so the eyes,
      // brows, and cheeks render unobstructed underneath.
      return (
        <g>
          <path
            d="M11 16 Q11 7 28 6 Q45 7 45 16 L45 52 Q42 43 39 36 L39 16 Q28 13 17 16 L17 36 Q14 43 11 52 Z"
            fill={color}
          />
          {/* Subtle center-part shadow on the crown above the hairline */}
          <path d="M28 7 L28 13" stroke="#000" strokeWidth="0.5" opacity="0.3" fill="none" />
          {/* Small gold stud earrings */}
          <circle cx="13.5" cy="32" r="1" fill="#d4af37" />
          <circle cx="42.5" cy="32" r="1" fill="#d4af37" />
        </g>
      );
    case 'bun_updo':
      // Female avatar — hair pulled into a tidy bun. CRITICAL: face oval
      // stays fully visible. The hairline cap covers ONLY the crown
      // (above the brows), the bun sits on top of the head, and the
      // forehead + face stay clear.
      return (
        <g>
          {/* Hairline cap — covers the crown only, stops well above brows (y=17) */}
          <path d="M12 16 Q12 8 28 7 Q44 8 44 16 Q40 13 28 13 Q16 13 12 16 Z" fill={color} />
          {/* Bun on top of the head */}
          <ellipse cx="28" cy="6" rx="5" ry="3.5" fill={color} />
          <ellipse cx="28" cy="5" rx="3.2" ry="2" fill="#000" opacity="0.18" />
          {/* Soft sideburn wisps in front of (covering) the ears */}
          <path d="M13 17 L13 26" stroke={color} strokeWidth="2.6" strokeLinecap="round" />
          <path d="M43 17 L43 26" stroke={color} strokeWidth="2.6" strokeLinecap="round" />
          {/* Small gold drop earrings */}
          <circle cx="13.5" cy="33" r="1" fill="#d4af37" />
          <circle cx="42.5" cy="33" r="1" fill="#d4af37" />
        </g>
      );
    default:
      return null;
  }
}

// Priya's portrait is canonical — same face that appears in the left-panel
// Manager's Cabin scene (extracted verbatim from src/assets/scenes/cabin.svg
// so the two stay pixel-identical). All chat / message / Day-1 / profile
// renders of Priya now route through this single component so she looks the
// same everywhere she appears.
function PriyaPortraitSVG({ size = 56, expression = 'neutral' }) {
  const mouth = {
    happy:     'M -8 52 Q 0 58 8 52',
    excited:   'M -10 50 Q 0 60 10 50 Z',
    thinking:  'M -4 54 L 4 54',
    concerned: 'M -8 56 Q 0 52 8 56',
    proud:     'M -6 52 Q 0 54 6 52',
    neutral:   'M -6 54 L 6 54',
  }[expression] || 'M -6 54 L 6 54';

  return (
    <svg
      viewBox="-50 -10 100 95"
      width={size}
      height={size}
      role="img"
      aria-label={`Priya Sharma (${expression})`}
      className="shrink-0"
    >
      {/* Soft halo behind head */}
      <circle cx="0" cy="36" r="44" fill="#2a3545" opacity="0.16" />
      {/* Blazer shoulders */}
      <path d="M -42 78 Q -42 70 0 65 Q 42 70 42 78 L 48 95 L -48 95 Z" fill="#2a3545" />
      {/* Collar / shirt */}
      <path d="M -8 78 L 0 70 L 8 78 L 4 84 L -4 84 Z" fill="#f0e6d3" />
      {/* Blazer lapels */}
      <path d="M -12 78 L -22 92 L -14 84 Z" fill="#1f2735" />
      <path d="M 12 78 L 22 92 L 14 84 Z" fill="#1f2735" />
      {/* Neck */}
      <rect x="-7" y="52" width="14" height="20" fill="#c8845a" />
      {/* Head */}
      <circle cx="0" cy="36" r="32" fill="#c8845a" />
      {/* Hair (bun at back + part on side) */}
      <path d="M -32 30 Q -32 4 0 0 Q 32 4 32 30 L 32 36 Q 26 14 0 14 Q -26 14 -32 36 Z" fill="#1a0f0a" />
      <circle cx="-4" cy="-2" r="9" fill="#1a0f0a" />
      {/* Ears */}
      <ellipse cx="-30" cy="38" rx="3" ry="4" fill="#c8845a" />
      <ellipse cx="30"  cy="38" rx="3" ry="4" fill="#c8845a" />
      {/* Brows */}
      <path d="M -16 30 L -8 28" stroke="#1a0f0a" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M 8 28 L 16 30"   stroke="#1a0f0a" strokeWidth="2.5" strokeLinecap="round" />
      {/* Glasses */}
      <g stroke="#1a0f0a" strokeWidth="1.5" fill="none">
        <rect x="-18" y="34" width="14" height="10" rx="2" />
        <rect x="4"   y="34" width="14" height="10" rx="2" />
        <line x1="-4" y1="39" x2="4" y2="39" />
      </g>
      {/* Eyes behind glasses */}
      <ellipse cx="-11" cy="39" rx="2.5" ry="2.8" fill="#1a0f0a" />
      <ellipse cx="11"  cy="39" rx="2.5" ry="2.8" fill="#1a0f0a" />
      <circle cx="-12" cy="38" r="0.7" fill="#fff5e4" />
      <circle cx="10"  cy="38" r="0.7" fill="#fff5e4" />
      {/* Nose */}
      <circle cx="0" cy="46" r="0.8" fill="#8a4f2a" opacity="0.5" />
      {/* Mouth — varies by expression */}
      <path d={mouth} stroke="#1a0f0a" strokeWidth="2" strokeLinecap="round" fill="none" />
      {/* Blush */}
      <ellipse cx="-22" cy="47" rx="3" ry="2" fill="#e89270" opacity="0.5" />
      <ellipse cx="22"  cy="47" rx="3" ry="2" fill="#e89270" opacity="0.5" />
    </svg>
  );
}


export default function CharacterAvatar({
  character = 'priya',
  expression = 'neutral',
  avatarId = 'avatar_02',
  size = 56,
}) {
  // Priya gets the canonical cabin-scene portrait everywhere.
  if (character === 'priya') {
    return <PriyaPortraitSVG size={size} expression={expression} />;
  }

  let c;
  if (character === 'player') {
    const variant = PLAYER_AVATARS[avatarId] || PLAYER_AVATARS.avatar_02;
    c = { ...CHARACTERS.player, ...variant };
  } else {
    c = CHARACTERS[character] || CHARACTERS.priya;
  }
  const e = EXPRESSIONS[expression] || EXPRESSIONS.neutral;

  return (
    <svg
      viewBox="0 0 56 56"
      width={size}
      height={size}
      role="img"
      aria-label={`${c.label || 'character'} (${expression})`}
      className="shrink-0"
    >
      {/* Soft halo behind head — gives the avatar weight against dark scene */}
      <circle cx="28" cy="28" r="26" fill={c.accent || '#3d2b1f'} opacity="0.16" />

      {/* Shoulders / blazer */}
      <path d="M4 56 Q4 42 28 42 Q52 42 52 56 Z" fill={c.accent || '#3d2b1f'} />
      <path d="M14 56 Q14 46 28 46 Q42 46 42 56 Z" fill={c.accent2 || c.accent || '#3d2b1f'} opacity="0.65" />

      {/* Head — slightly squashed sphere */}
      <ellipse cx="28" cy="28" rx="15" ry="15.5" fill={c.skin || '#c8845a'} />

      {/* Hair (style varies per character / avatar) */}
      <Hair style={c.hairStyle} color={c.hair || '#1a0f0a'} />

      {/* Ears — suppressed for long-hair / headscarf styles where the hair
          already covers the temples; otherwise the ears poke through the
          hair and the silhouette reads androgynous. */}
      {!['priya_bun', 'zara_long', 'headscarf', 'long_open', 'bun_updo'].includes(c.hairStyle) && (
        <>
          <ellipse cx="13" cy="29" rx="2" ry="2.5" fill={c.skin || '#c8845a'} />
          <ellipse cx="43" cy="29" rx="2" ry="2.5" fill={c.skin || '#c8845a'} />
        </>
      )}

      {/* Brows */}
      <path d={e.brow} stroke="#1f1208" strokeWidth="2" strokeLinecap="round" fill="none" />

      {/* Eyes (or glasses + eyes) */}
      {c.glasses ? (
        <>
          <Eyes shape={e.eye} />
          <Glasses />
        </>
      ) : (
        <Eyes shape={e.eye} />
      )}

      {/* Optional cheek blush for happy/excited */}
      {e.blush && <Blush />}

      {/* Nose tip — single small mark for warmth */}
      <circle cx="28" cy="32" r="0.7" fill="#1f1208" opacity="0.35" />

      {/* Mouth */}
      <path d={e.mouth} stroke="#1f1208" strokeWidth="2" strokeLinecap="round" fill="none" />

      {/* Stubble overlay for Arjun */}
      {c.stubble && <Stubble />}
    </svg>
  );
}

export function characterMeta(character, avatarId) {
  if (character === 'player') {
    const variant = PLAYER_AVATARS[avatarId] || PLAYER_AVATARS.avatar_02;
    return { ...CHARACTERS.player, ...variant };
  }
  return CHARACTERS[character] || CHARACTERS.priya;
}
