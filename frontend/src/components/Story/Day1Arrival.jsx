import { useEffect, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

// Plays once between onboarding and the office reveal. Spec §3:
// Phase 1: NxtCorp logo on black
// Phase 2: "Hyderabad, Monday Morning"
// Phase 3: scene fades in (we lift the curtain — App swaps to office)
// Phase 4: "Your first day"
// Phase 5: full reveal — Priya is already typing
export default function Day1Arrival({ open, onDone }) {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (!open) {
      setPhase(0);
      return;
    }
    const schedule = reduce
      ? [[1, 0], [2, 300], [3, 500]]
      : [
          [1, 600],   // location text
          [2, 2000],  // "Your first day"
          [3, 3600],  // done — call onDone, curtain lifts
        ];
    const timers = schedule.map(([p, ms]) =>
      setTimeout(() => {
        setPhase(p);
        if (p === 3) onDone();
      }, ms),
    );
    return () => timers.forEach(clearTimeout);
  }, [open, reduce, onDone]);

  return (
    <AnimatePresence>
      {open && phase < 3 && (
        <motion.div
          key="d1-curtain"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 1.5 }}
          className="fixed inset-0 z-[57] bg-black grid place-items-center"
        >
          <motion.div
            key="d1-logo"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="flex flex-col items-center gap-2"
          >
            <div className="w-14 h-14 rounded-2xl bg-nxt-accent grid place-items-center text-white font-display text-2xl shadow-gold">
              N
            </div>
            <div className="font-display text-lg text-nxt-text">NxtCorp</div>
            {phase >= 1 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.85 }}
                transition={{ duration: 0.8 }}
                className="text-sm text-nxt-muted tracking-wider mt-3"
              >
                Hyderabad · Monday morning
              </motion.div>
            )}
            {phase >= 2 && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
                className="text-base text-nxt-gold tracking-wide mt-2 font-display"
              >
                Your first day.
              </motion.div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
