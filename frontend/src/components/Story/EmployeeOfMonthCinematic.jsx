import { useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';

// Full-screen celebration when the player wins Employee of the Month.
// Triggered from App.jsx by RunResponse.employee_of_month_awarded.
// Auto-dismisses after ~6s, or on click anywhere.
function StarRain() {
  const reduce = useReducedMotion();
  if (reduce) return null;
  const stars = Array.from({ length: 24 }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    delay: Math.random() * 1.5,
    size: 10 + Math.random() * 16,
    rotate: (Math.random() * 60) - 30,
  }));
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {stars.map((s) => (
        <motion.div
          key={s.id}
          initial={{ y: -40, opacity: 0, rotate: 0 }}
          animate={{ y: '110vh', opacity: [0, 1, 1, 0], rotate: s.rotate * 6 }}
          transition={{ duration: 4.5, ease: 'easeIn', delay: s.delay, times: [0, 0.1, 0.85, 1] }}
          style={{
            position: 'absolute',
            left: s.left,
            fontSize: s.size,
            color: '#ffd700',
            filter: 'drop-shadow(0 0 6px rgba(255,215,0,0.7))',
          }}
        >
          ★
        </motion.div>
      ))}
    </div>
  );
}

export default function EmployeeOfMonthCinematic({ award, profile, onDismiss }) {
  // award: { yearMonth, displayName, stats?: {...} } | null
  useEffect(() => {
    if (!award) return undefined;
    const t = setTimeout(() => onDismiss?.(), 6000);
    return () => clearTimeout(t);
  }, [award, onDismiss]);

  return (
    <AnimatePresence>
      {award && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="fixed inset-0 z-[60] grid place-items-center bg-black/80 backdrop-blur-sm cursor-pointer"
          onClick={onDismiss}
          role="dialog"
          aria-modal="true"
          aria-label="Employee of the Month"
        >
          <StarRain />

          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.8, opacity: 0 }}
            transition={{ duration: 0.5, type: 'spring', stiffness: 200, damping: 18 }}
            className="relative max-w-lg w-[90vw] bg-gradient-to-br from-amber-500/95 via-amber-400/95 to-yellow-300/95 rounded-3xl shadow-2xl border-4 border-yellow-200 p-8 text-center text-stone-900"
          >
            <div className="text-7xl mb-2 leading-none">🌟</div>
            <div className="text-xs uppercase tracking-[0.4em] text-stone-700 mb-1">
              {award.yearMonth}
            </div>
            <h1 className="font-display text-3xl mb-1">Employee of the Month</h1>

            <div className="flex items-center justify-center gap-2 mt-3 mb-4">
              <CharacterAvatar
                character="player"
                avatarId={profile?.avatar_id || 'avatar_02'}
                expression="excited"
                size={48}
              />
              <div className="font-display text-xl">{award.displayName || profile?.display_name}</div>
            </div>

            <p className="text-sm leading-relaxed text-stone-800 mb-4">
              Ravi Sir made the call. Clean delivery, kept the streak, hit your first-try
              targets without leaning on hints. The team noticed.
            </p>

            <div className="rounded-xl bg-stone-900/15 border border-stone-900/20 px-4 py-2 text-sm font-medium">
              +200 XP awarded
            </div>

            <div className="mt-5 text-[11px] text-stone-700/70 italic">
              click anywhere to dismiss
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
