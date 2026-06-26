import { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import SkillProfile from './SkillProfile.jsx';

export default function ProfileModal({ profile, open, onClose }) {
  useEffect(() => {
    if (!open) return;
    function onKey(e) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="profile-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/55 backdrop-blur grid place-items-center p-6 z-50"
          role="dialog"
          aria-modal="true"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 220, damping: 22 }}
            className="relative"
            onClick={(e) => e.stopPropagation()}
          >
            <SkillProfile profile={profile} />
            <button
              type="button"
              onClick={onClose}
              className="absolute top-3 right-3 w-7 h-7 rounded-full hover:bg-nxt-panel grid place-items-center text-nxt-muted hover:text-nxt-text"
              aria-label="Close profile"
            >
              ✕
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
