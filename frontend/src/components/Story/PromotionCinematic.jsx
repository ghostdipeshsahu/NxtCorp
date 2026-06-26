import { useEffect, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';
import Typewriter from '../UI/Typewriter.jsx';

// Confetti via a small set of motion divs — no extra dep.
function ConfettiBurst() {
  const reduce = useReducedMotion();
  if (reduce) return null;
  const pieces = Array.from({ length: 40 }, (_, i) => {
    const angle = (i / 40) * Math.PI * 2;
    const dx = Math.cos(angle) * (160 + Math.random() * 80);
    const dy = -200 - Math.random() * 200;
    const colors = ['#ffd700', '#e94560', '#4a9eff', '#00d4aa', '#ffffff'];
    return {
      id: i,
      dx,
      dy,
      color: colors[i % colors.length],
      rotate: 360 + Math.random() * 360,
      delay: Math.random() * 0.15,
    };
  });
  return (
    <div className="absolute inset-0 grid place-items-center pointer-events-none overflow-hidden">
      {pieces.map((p) => (
        <motion.div
          key={p.id}
          initial={{ x: 0, y: 0, opacity: 0, rotate: 0 }}
          animate={{ x: p.dx, y: p.dy, opacity: [0, 1, 1, 0], rotate: p.rotate }}
          transition={{ duration: 1.4, ease: 'easeOut', delay: p.delay, times: [0, 0.1, 0.7, 1] }}
          style={{ width: 8, height: 14, background: p.color, position: 'absolute' }}
        />
      ))}
    </div>
  );
}

// Phases roughly per spec §3. Times are seconds since mount.
const RAVI_TEMPLATE = (name) =>
  `${name}, I've been watching your work. The team has noticed your growth. Effective today, you're being promoted.`;

export default function PromotionCinematic({ open, displayName, newTitle, onDismiss }) {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (!open) {
      setPhase(0);
      return;
    }
    // Schedule the phases. With reduced motion, skip ahead aggressively.
    const schedule = reduce
      ? [[1, 0], [2, 0], [3, 50], [4, 100], [5, 1500], [6, 1500]]
      : [
          [1, 500],   // logo
          [2, 1500],  // Ravi slides in
          [3, 2500],  // message types
          [4, 4000],  // title glow
          [5, 5000],  // confetti
          [6, 6500],  // "press any key"
        ];
    const timers = schedule.map(([p, ms]) => setTimeout(() => setPhase(p), ms));
    return () => timers.forEach(clearTimeout);
  }, [open, reduce]);

  useEffect(() => {
    if (!open) return;
    function onKey() {
      if (phase >= 4) onDismiss();
    }
    window.addEventListener('keydown', onKey);
    window.addEventListener('click', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('click', onKey);
    };
  }, [open, phase, onDismiss]);

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="promo-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.5 }}
        className="fixed inset-0 z-[60] bg-black/90 backdrop-blur grid place-items-center text-center"
        role="dialog"
        aria-modal="true"
      >
        {/* Phase 1: NxtCorp logo */}
        {phase >= 1 && (
          <motion.div
            className="absolute top-1/4 -translate-y-1/2 left-0 right-0 flex flex-col items-center gap-2"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <div className="w-16 h-16 rounded-2xl bg-nxt-accent grid place-items-center text-white font-display text-3xl shadow-gold">
              N
            </div>
            <div className="font-display text-xl text-nxt-gold">NxtCorp</div>
          </motion.div>
        )}

        {/* Phase 2+: Ravi avatar slides in from the right */}
        {phase >= 2 && (
          <motion.div
            initial={{ x: 200, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 80, damping: 14 }}
            className="absolute left-1/2 -translate-x-1/2 top-1/2 -translate-y-1/2 flex flex-col items-center gap-3"
          >
            <CharacterAvatar character="ravi" expression="proud" size={120} />

            {/* Phase 3+: Ravi types his line */}
            {phase >= 3 && (
              <div className="max-w-md text-base text-white font-display leading-relaxed">
                <Typewriter text={RAVI_TEMPLATE(displayName)} charDelay={28} />
              </div>
            )}

            {/* Phase 4+: New title with gold glow */}
            {phase >= 4 && (
              <motion.div
                initial={{ scale: 0.85, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                className="mt-4 px-5 py-2 rounded-xl text-2xl font-display text-nxt-gold shadow-gold"
                style={{
                  background:
                    'linear-gradient(180deg, rgba(255,215,0,0.10), rgba(255,215,0,0.04))',
                  border: '1px solid rgba(255,215,0,0.35)',
                }}
              >
                {newTitle}
              </motion.div>
            )}
          </motion.div>
        )}

        {/* Phase 5: Confetti */}
        {phase >= 5 && <ConfettiBurst />}

        {/* Phase 6: Press any key */}
        {phase >= 6 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.7 }}
            transition={{ duration: 0.5 }}
            className="absolute bottom-12 text-sm text-white/70 tracking-wide"
          >
            Press any key to continue
          </motion.div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
