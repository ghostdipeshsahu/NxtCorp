import CharacterAvatar from '../Chat/CharacterAvatar.jsx';
import { getCharacterPortrait, getSceneBackground } from '../../assets/index.js';

// Pure CSS/HTML cabin scene. No canvas, no fancy gradients. The room is
// stacked back-to-front:
//
//   [floor label]
//   [back wall — solid warm brown]
//     [window — night sky rectangle with scattered orange dots]
//     [NxtCorp logo on wall]
//   [desk — wooden brown rectangle covering bottom half]
//     [lamp glow circle behind everything on the desk]
//     [Priya avatar, sitting at desk]
//     [lamp body — small block + arm + bulb on desk surface]
//     [nameplate strip]

// Build a CSS box-shadow value that places ~20 small orange dots in the
// window. One invisible 1x1 div carries all the box-shadows — much cheaper
// than 20 absolute-positioned children.
function buildCityLights(seedStr = 'nxtcorp') {
  let s = 0;
  for (let i = 0; i < seedStr.length; i++) s = (s * 31 + seedStr.charCodeAt(i)) >>> 0;
  const rand = () => {
    s = (s * 1103515245 + 12345) >>> 0;
    return (s & 0x7fffffff) / 0x7fffffff;
  };
  const dots = [];
  for (let i = 0; i < 20; i++) {
    const x = Math.round(8 + rand() * 220);
    const y = Math.round(8 + rand() * 80);
    const big = rand() > 0.7;
    const size = big ? 2 : 1;
    const alpha = (0.55 + rand() * 0.45).toFixed(2);
    dots.push(`${x}px ${y}px 0 ${size}px rgba(245,166,35,${alpha})`);
  }
  return dots.join(', ');
}

export default function CabinScene({ priyaExpression = 'happy' }) {
  const lights = buildCityLights('cabin-v1');
  const bgUrl = getSceneBackground('cabin');
  const priyaPortrait = getCharacterPortrait('priya', priyaExpression);

  // If the user dropped a real illustrated background in
  // src/assets/scenes/cabin.{png,jpg,webp}, render the IMAGE-FIRST layout:
  // full-bleed image + a soft vignette + the floor label + Priya portrait
  // (if provided) + nameplate. No CSS-scenery clutter on top.
  if (bgUrl) {
    return (
      <div className="relative h-full w-full overflow-hidden rounded-2xl border border-nxt-border shadow-panel">
        <img
          src={bgUrl}
          alt="Manager's cabin"
          className="absolute inset-0 w-full h-full object-cover"
          draggable={false}
        />
        {/* Soft top-to-bottom darken so UI text stays readable */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'linear-gradient(180deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 70%, rgba(0,0,0,0.55) 100%)',
          }}
        />
        <div className="absolute top-3 left-3 z-20 text-[10px] uppercase tracking-[0.18em] text-white/85">
          Manager's Cabin · Hyderabad Office
        </div>
        {priyaPortrait && (
          <img
            src={priyaPortrait}
            alt="Priya"
            className="absolute"
            style={{
              bottom: '8%',
              left: '50%',
              transform: 'translateX(-50%)',
              height: '60%',
              filter: 'drop-shadow(0 10px 16px rgba(0,0,0,0.55))',
            }}
            draggable={false}
          />
        )}
        <div
          className="absolute"
          style={{
            bottom: '3%',
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '3px 12px',
            background: 'rgba(20,15,10,0.85)',
            border: '1px solid #5a3f2e',
            borderRadius: '3px',
            color: '#f0e6d3',
            fontSize: '10px',
            letterSpacing: '0.1em',
            fontFamily: 'Fraunces, Georgia, serif',
            boxShadow: '0 4px 8px rgba(0,0,0,0.5)',
          }}
        >
          PRIYA SHARMA · SENIOR DEV
        </div>
      </div>
    );
  }

  // ===== Fallback: original CSS scene =====
  return (
    <div
      className="relative h-full w-full overflow-hidden rounded-2xl border border-nxt-border shadow-panel"
      style={{ background: '#12100e' }}
    >
      {/* Floor label */}
      <div className="absolute top-3 left-3 z-20 text-[10px] uppercase tracking-[0.18em] text-nxt-muted">
        Manager's Cabin · Hyderabad Office
      </div>

      {/* ===== Back wall ===== */}
      <div className="absolute top-0 left-0 right-0" style={{ height: '60%', background: '#1a1510' }} />

      {/* ===== Window ===== */}
      <div
        className="absolute"
        style={{
          top: '14%',
          left: '12%',
          width: '52%',
          height: '34%',
          background: '#0a0a1a',
          border: '4px solid #3d2b1f',
          borderRadius: '4px',
          boxShadow: 'inset 0 0 24px rgba(0,0,0,0.6)',
          overflow: 'hidden',
        }}
      >
        {/* City lights — 1x1 div with box-shadow scatter */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '1px',
            height: '1px',
            background: 'transparent',
            boxShadow: lights,
          }}
        />
        {/* Window cross mullion */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: '50%',
            width: '2px',
            background: '#3d2b1f',
            transform: 'translateX(-50%)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: '50%',
            height: '2px',
            background: '#3d2b1f',
            transform: 'translateY(-50%)',
          }}
        />
        {/* Horizon glow strip */}
        <div
          style={{
            position: 'absolute',
            bottom: 6,
            left: 0,
            right: 0,
            height: '1px',
            background: 'rgba(245,166,35,0.35)',
          }}
        />
      </div>

      {/* ===== NxtCorp wall logo ===== */}
      <div
        className="absolute font-display tracking-widest"
        style={{
          top: '12%',
          right: '8%',
          color: '#f5c842',
          fontSize: '0.85rem',
          opacity: 0.9,
          textShadow: '0 0 12px rgba(245,200,66,0.25)',
        }}
      >
        NxtCorp
      </div>
      <div
        className="absolute"
        style={{
          top: 'calc(12% + 1.4rem)',
          right: '8%',
          fontSize: '0.55rem',
          letterSpacing: '0.25em',
          color: '#8a7a6a',
        }}
      >
        EST · BENGALURU
      </div>

      {/* ===== Desk surface (bottom 40%) ===== */}
      <div
        className="absolute left-0 right-0"
        style={{
          bottom: 0,
          height: '40%',
          background: 'linear-gradient(180deg, #4a3528 0%, #3d2b1f 60%, #2a1d14 100%)',
          borderTop: '2px solid #5a3f2e',
          boxShadow: '0 -10px 30px -10px rgba(0,0,0,0.7)',
        }}
      >
        {/* Desk edge highlight */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '2px',
            background: 'rgba(245,166,35,0.4)',
          }}
        />
        {/* Faint wood grain lines */}
        <div
          style={{
            position: 'absolute',
            top: '20%',
            left: '6%',
            right: '6%',
            height: '1px',
            background: 'rgba(74,53,40,0.6)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: '55%',
            left: '12%',
            right: '20%',
            height: '1px',
            background: 'rgba(74,53,40,0.5)',
          }}
        />
      </div>

      {/* ===== Lamp glow halo ===== */}
      <div
        className="absolute pointer-events-none"
        style={{
          bottom: '18%',
          left: '14%',
          width: 180,
          height: 180,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(245,166,35,0.42) 0%, rgba(245,166,35,0.16) 40%, rgba(245,166,35,0) 75%)',
        }}
      />

      {/* ===== Priya — centered, sitting behind the desk ===== */}
      <div
        className="absolute"
        style={{
          bottom: '20%',
          left: '50%',
          transform: 'translateX(-50%)',
          filter: 'drop-shadow(0 6px 8px rgba(0,0,0,0.5))',
        }}
      >
        <CharacterAvatar character="priya" expression={priyaExpression} size={96} />
      </div>

      {/* ===== Lamp on the desk ===== */}
      <div
        className="absolute"
        style={{
          bottom: '8%',
          left: '20%',
          width: 36,
          height: 64,
        }}
      >
        {/* base */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 20,
            height: 4,
            background: '#2a1d14',
            borderRadius: '2px',
          }}
        />
        {/* arm */}
        <div
          style={{
            position: 'absolute',
            bottom: 4,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 3,
            height: 36,
            background: '#3d2b1f',
          }}
        />
        {/* shade */}
        <div
          style={{
            position: 'absolute',
            bottom: 36,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 28,
            height: 18,
            background: '#3d2b1f',
            borderTopLeftRadius: '14px 12px',
            borderTopRightRadius: '14px 12px',
            borderBottom: '2px solid #f5a623',
          }}
        />
        {/* bulb glow */}
        <div
          style={{
            position: 'absolute',
            bottom: 32,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 16,
            height: 6,
            borderRadius: '50%',
            background: '#f5a623',
            boxShadow: '0 0 24px 8px rgba(245,166,35,0.6)',
          }}
        />
      </div>

      {/* ===== Coffee mug ===== */}
      <div
        className="absolute"
        style={{
          bottom: 'calc(8% + 4px)',
          right: '18%',
        }}
      >
        <div
          style={{
            width: 22,
            height: 26,
            background: '#6b4226',
            border: '1px solid #2a1d14',
            borderRadius: '2px 2px 4px 4px',
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 3,
              left: 3,
              right: 3,
              height: 4,
              background: '#2a1d14',
              borderRadius: '50%',
            }}
          />
          <div
            style={{
              position: 'absolute',
              right: -8,
              top: 5,
              width: 8,
              height: 12,
              border: '2px solid #6b4226',
              borderLeft: 'none',
              borderRadius: '0 8px 8px 0',
            }}
          />
        </div>
      </div>

      {/* ===== Nameplate ===== */}
      <div
        className="absolute"
        style={{
          bottom: '4%',
          left: '50%',
          transform: 'translateX(-50%)',
          padding: '3px 10px',
          background: '#2a1d14',
          border: '1px solid #5a3f2e',
          borderRadius: '3px',
          color: '#f0e6d3',
          fontSize: '10px',
          letterSpacing: '0.08em',
          fontFamily: 'Fraunces, Georgia, serif',
          boxShadow: '0 4px 6px rgba(0,0,0,0.5)',
        }}
      >
        PRIYA SHARMA · SENIOR DEV
      </div>

      {/* ===== Vignette ===== */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse at 50% 55%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.55) 100%)',
        }}
      />
    </div>
  );
}
