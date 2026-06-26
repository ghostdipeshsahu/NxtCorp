import { useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

// Brief celebration after passing every hidden test on the first attempt.
// Spec §3: full-screen white flash, banner slides down, holds, slides up.
export default function FirstTryBanner({ open, onDone }) {
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const id = setTimeout(onDone, reduce ? 1200 : 2400);
    return () => clearTimeout(id);
  }, [open, onDone, reduce]);

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="ft-flash"
        initial={{ opacity: 0 }}
        animate={reduce ? { opacity: 0 } : { opacity: [0, 0.3, 0] }}
        transition={{ duration: 0.4, times: [0, 0.4, 1] }}
        className="fixed inset-0 z-[58] pointer-events-none bg-white"
      />
      <motion.div
        key="ft-banner"
        initial={{ y: -60, opacity: 0 }}
        animate={{
          y: reduce ? 16 : [-60, 16, 16, -60],
          opacity: reduce ? 1 : [0, 1, 1, 0],
        }}
        transition={{ duration: 2.2, times: [0, 0.2, 0.85, 1], ease: 'easeOut' }}
        className="fixed left-1/2 top-4 -translate-x-1/2 z-[59] px-5 py-2 rounded-xl text-base font-display font-medium text-white shadow-gold"
        style={{
          background: 'linear-gradient(90deg, #e94560, #ffd700)',
        }}
      >
        FIRST TRY! 🎯
      </motion.div>
    </AnimatePresence>
  );
}
