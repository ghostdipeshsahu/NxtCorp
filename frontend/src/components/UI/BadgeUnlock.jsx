import { useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

// Same map shape as SkillProfile so badges look consistent everywhere.
const META = {
  first_try: { label: 'First Try', icon: '🎯', blurb: 'Passed hidden tests on the first attempt.' },
  eagle_eye: { label: 'Eagle Eye', icon: '🦅', blurb: 'Found every gap in a code review.' },
  bug_hunter: { label: 'Bug Hunter', icon: '🐛', blurb: 'Wrote a test that caught a real bug.' },
  precision_fix: { label: 'Precision Fix', icon: '🔧', blurb: 'Fixed a prompt at exactly the right place.' },
  week_warrior: { label: 'Week Warrior', icon: '🔥', blurb: '7-day streak.' },
  unstoppable: { label: 'Unstoppable', icon: '🚀', blurb: '30-day streak.' },
  first_promotion: { label: 'First Promotion', icon: '🏆', blurb: 'Earned your first level-up.' },
  project_complete: { label: 'Project Complete', icon: '🧱', blurb: 'Finished a full project arc.' },
  employee_of_the_month: { label: 'Employee of the Month', icon: '🌟', blurb: 'Cleared tasks without coffee-corner hints.' },
};

function Sparkles() {
  const reduce = useReducedMotion();
  if (reduce) return null;
  return (
    <div className="absolute inset-0 grid place-items-center pointer-events-none">
      {Array.from({ length: 14 }).map((_, i) => {
        const angle = (i / 14) * Math.PI * 2;
        const dx = Math.cos(angle) * 60;
        const dy = Math.sin(angle) * 36;
        return (
          <motion.div
            key={i}
            initial={{ x: 0, y: 0, opacity: 0 }}
            animate={{ x: dx, y: dy, opacity: [0, 1, 0] }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
            className="w-1.5 h-1.5 rounded-full bg-nxt-gold"
            style={{ position: 'absolute' }}
          />
        );
      })}
    </div>
  );
}

// Single-badge toast: appears top-right, sparkle burst, auto-dismiss.
function BadgeToast({ badgeKey, onDismiss }) {
  const reduce = useReducedMotion();
  const meta = META[badgeKey] || { label: badgeKey, icon: '✨', blurb: '' };

  useEffect(() => {
    const id = setTimeout(onDismiss, 3000);
    return () => clearTimeout(id);
  }, [onDismiss]);

  return (
    <motion.button
      type="button"
      onClick={onDismiss}
      initial={{ x: 80, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 80, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 250, damping: 22 }}
      className="relative flex items-center gap-3 px-3 py-2 rounded-xl bg-nxt-surface border border-nxt-gold/40 shadow-gold cursor-pointer"
      title="Click to dismiss"
    >
      <Sparkles />
      <motion.div
        initial={{ rotate: 0, scale: 0 }}
        animate={reduce ? { scale: 1 } : { rotate: 360, scale: 1 }}
        transition={{ duration: 0.7, ease: 'easeOut' }}
        className="text-2xl"
      >
        {meta.icon}
      </motion.div>
      <div className="text-left">
        <div className="text-[10px] uppercase tracking-wider text-nxt-gold">Badge unlocked</div>
        <div className="text-sm font-medium text-nxt-text">{meta.label}</div>
        <div className="text-[11px] text-nxt-muted leading-tight">{meta.blurb}</div>
      </div>
    </motion.button>
  );
}

export default function BadgeUnlock({ queue, onDismiss }) {
  return (
    <div className="fixed top-16 right-4 z-[55] flex flex-col gap-2">
      <AnimatePresence>
        {queue.map((key) => (
          <BadgeToast key={key} badgeKey={key} onDismiss={() => onDismiss(key)} />
        ))}
      </AnimatePresence>
    </div>
  );
}
