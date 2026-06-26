import { motion, useReducedMotion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';

// Spec §1, Layer 3: character planes with subtle idle animations.
// Breathing scale, occasional head tilt. Lives in the React/DOM layer above
// the Three canvas — keeps SVG rendering cheap and crisp.

function IdleCharacter({ character, expression, size = 64, label, role, accent }) {
  const reduce = useReducedMotion();

  const breathing = reduce
    ? {}
    : {
        scale: [1, 1.018, 1],
        transition: { duration: 3, repeat: Infinity, ease: 'easeInOut' },
      };

  // Tilt every 4-8s with a randomized stagger via initial offset.
  const tilt = reduce
    ? {}
    : {
        rotate: [0, 2.2, 0, -2, 0],
        transition: {
          duration: 6,
          repeat: Infinity,
          repeatDelay: Math.random() * 2.5,
          ease: 'easeInOut',
          times: [0, 0.2, 0.5, 0.8, 1],
        },
      };

  return (
    <div className="flex flex-col items-center gap-1 pointer-events-none">
      <motion.div animate={tilt} style={{ transformOrigin: 'bottom center' }}>
        <motion.div animate={breathing} style={{ transformOrigin: 'bottom center' }}>
          <CharacterAvatar character={character} expression={expression} size={size} />
        </motion.div>
      </motion.div>
      {/* Soft shadow beneath */}
      <div
        className="rounded-full"
        style={{
          width: size * 0.6,
          height: size * 0.08,
          background:
            'radial-gradient(ellipse at center, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 70%)',
          marginTop: -6,
        }}
      />
      {label && (
        <div
          className="text-[10px] px-2 py-0.5 rounded-full backdrop-blur bg-black/40 text-white/85"
          style={{
            border: `1px solid ${accent || 'rgba(255,255,255,0.15)'}`,
          }}
        >
          {label}
          {role && <span className="text-white/40"> · {role}</span>}
        </div>
      )}
    </div>
  );
}

export default function Characters({ priyaExpression = 'neutral' }) {
  return (
    <div className="absolute inset-x-0 bottom-6 flex items-end justify-around px-6 pointer-events-none">
      <IdleCharacter
        character="arjun"
        expression="neutral"
        size={64}
        label="Arjun"
        accent="rgba(63,124,172,0.45)"
      />
      <IdleCharacter
        character="priya"
        expression={priyaExpression}
        size={92}
        label="Priya"
        role="Manager"
        accent="rgba(247,126,44,0.55)"
      />
      <IdleCharacter
        character="zara"
        expression="thinking"
        size={60}
        label="Zara"
        role="QA"
        accent="rgba(123,61,199,0.4)"
      />
    </div>
  );
}
