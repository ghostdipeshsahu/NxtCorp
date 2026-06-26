import { useEffect } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

// Direction map: which way does the walker exit during scene transitions.
//   desk    -> cabin   : LEFT
//   cabin   -> desk    : RIGHT
//   desk    -> coffee  : RIGHT
//   coffee  -> desk    : LEFT
//   cabin   -> coffee  : RIGHT (rare; falls through)
//   coffee  -> cabin   : LEFT
function directionFor(from, to) {
  const leftPairs = new Set([
    'desk->cabin',
    'coffee->desk',
    'coffee->cabin',
  ]);
  return leftPairs.has(`${from}->${to}`) ? 'left' : 'right';
}

function Walker({ direction, label }) {
  const flip = direction === 'left' ? -1 : 1;
  return (
    <div className="flex flex-col items-center" style={{ transform: `scaleX(${flip})` }}>
      <div className="text-[9px] mb-1 text-nxt-text bg-nxt-cabin/85 px-1.5 py-0.5 rounded"
           style={{ transform: `scaleX(${flip})` }}>
        {label}
      </div>
      {/* Body */}
      <div className="relative" style={{ width: 22, height: 36 }}>
        {/* head */}
        <div className="absolute left-1/2 -translate-x-1/2 top-0 w-5 h-5 rounded-full bg-nxt-skin"
             style={{ background: '#c8845a' }} />
        {/* torso */}
        <div className="absolute left-1/2 -translate-x-1/2 top-5 w-3 h-7 rounded-sm"
             style={{ background: '#e8854a' }} />
        {/* arms */}
        <div className="absolute left-0 top-6 w-1 h-5 origin-top animate-armLeft"
             style={{ background: '#c8845a' }} />
        <div className="absolute right-0 top-6 w-1 h-5 origin-top animate-armRight"
             style={{ background: '#c8845a' }} />
        {/* legs */}
        <div className="absolute left-2 bottom-0 w-1 h-7 origin-top animate-legLeft"
             style={{ background: '#3d2b1f' }} />
        <div className="absolute right-2 bottom-0 w-1 h-7 origin-top animate-legRight"
             style={{ background: '#3d2b1f' }} />
      </div>
      {/* shadow */}
      <div className="w-6 h-1 rounded-full bg-black/40 mt-0.5 blur-[1px]" />
    </div>
  );
}

// Plays a full transition: walker traverses + warm fade-to-black + scene swap
// at midpoint + fade back in. `onMidpoint` is the moment to swap currentScene.
// `onComplete` runs after the new scene fade-in.
export default function WalkAnimation({
  from,
  to,
  playerName = 'You',
  onMidpoint,
  onComplete,
}) {
  const reduce = useReducedMotion();

  // Reduced motion: skip animation, fire midpoint + complete back to back.
  useEffect(() => {
    if (!reduce) return;
    onMidpoint && onMidpoint();
    const t = setTimeout(() => onComplete && onComplete(), 80);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduce]);

  if (reduce) return null;

  const dir = directionFor(from, to);
  const fromX = dir === 'left' ? '105%' : '-5%';
  const toX = dir === 'left' ? '-5%' : '105%';

  return (
    <div className="absolute inset-0 z-30 pointer-events-none">
      {/* Walker — traverses 0 -> 0.8s */}
      <motion.div
        className="absolute bottom-6"
        initial={{ left: fromX, opacity: 0 }}
        animate={{ left: toX, opacity: [0, 1, 1, 0] }}
        transition={{ duration: 0.8, ease: 'linear', times: [0, 0.15, 0.85, 1] }}
        style={{ width: 28 }}
      >
        <Walker direction={dir} label={playerName} />
      </motion.div>

      {/* Warm fade overlay — peaks at 0.95s, opacity 1 around midpoint */}
      <motion.div
        className="absolute inset-0"
        initial={{ opacity: 0 }}
        animate={{ opacity: [0, 0, 1, 1, 0] }}
        transition={{ duration: 1.5, times: [0, 0.5, 0.6, 0.75, 1], ease: 'easeInOut' }}
        style={{ backgroundColor: '#1a1410' }}
        onAnimationStart={() => {
          // Fire midpoint right when fade hits full opacity (~0.9s).
          setTimeout(() => onMidpoint && onMidpoint(), 900);
          setTimeout(() => onComplete && onComplete(), 1500);
        }}
      />
    </div>
  );
}
