import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import CountUp from '../UI/CountUp.jsx';
import { JOB_LEVEL_TOOLTIPS } from '../../content/levels.js';

function AnimatedProgressBar({ value }) {
  // value is 0..1
  const v = Math.min(1, Math.max(0, value || 0));
  return (
    <div className="w-32 h-2 rounded-full bg-nxt-panel overflow-hidden">
      <motion.div
        className="h-full rounded-full bg-gradient-to-r from-nxt-accent to-nxt-gold"
        initial={{ width: 0 }}
        animate={{ width: `${v * 100}%` }}
        transition={{ duration: 1.2, ease: 'easeOut' }}
      />
    </div>
  );
}

export default function TopBar({ profile, onLogout, onOpenProfile, onToggleSound, soundOn }) {
  const reduce = useReducedMotion();
  const currentXp = profile?.total_xp ?? 0;
  const lastXpRef = useRef(currentXp);
  const [bursts, setBursts] = useState([]); // floating "+N XP" texts

  useEffect(() => {
    if (currentXp > lastXpRef.current) {
      const delta = currentXp - lastXpRef.current;
      const id = Math.random().toString(36).slice(2);
      setBursts((b) => [...b, { id, value: delta }]);
      // Remove the burst after the animation has finished.
      const handle = setTimeout(
        () => setBursts((b) => b.filter((x) => x.id !== id)),
        1700,
      );
      lastXpRef.current = currentXp;
      return () => clearTimeout(handle);
    } else if (currentXp < lastXpRef.current) {
      lastXpRef.current = currentXp;
    }
  }, [currentXp]);

  return (
    <header className="relative bg-nxt-surface/85 backdrop-blur border-b border-nxt-border px-4 py-2 flex items-center gap-4 shadow-panel">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-nxt-accent grid place-items-center text-white font-display font-semibold shadow-panel">
          N
        </div>
        <div className="leading-tight">
          <div className="font-display text-base text-nxt-text">NxtCorp</div>
          <div className="text-[10px] uppercase tracking-wider text-nxt-muted">
            Hyderabad office
          </div>
        </div>
      </div>

      <div className="flex-1" />

      {profile && (
        <>
          <button
            type="button"
            onClick={onOpenProfile}
            className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-nxt-panel transition"
            title="View skills, badges, and progression"
          >
            <div className="text-right leading-tight">
              <div className="text-sm font-medium text-nxt-text">{profile.display_name}</div>
              <div
                className="text-xs text-nxt-accent cursor-help"
                title={JOB_LEVEL_TOOLTIPS[profile.job_level] || ''}
              >
                {profile.job_title}
              </div>
            </div>
          </button>

          <span
            className="px-2 py-0.5 rounded text-[10px] uppercase tracking-wider bg-nxt-panel border border-nxt-border text-nxt-muted"
            title="Current learning phase"
          >
            Phase {profile.progression_phase ?? '1'}
          </span>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 text-xs">
              <span className="text-nxt-muted">Lv</span>
              <span className="font-semibold text-nxt-text">{profile.job_level}</span>
            </div>
            <AnimatedProgressBar value={profile.progress_to_next_level ?? 0} />
            <div
              className="text-[10px] text-nxt-muted cursor-help"
              title={JOB_LEVEL_TOOLTIPS[(profile.job_level || 0) + 1] || ''}
            >
              {profile.next_level_title ? `→ ${profile.next_level_title}` : 'max'}
            </div>
          </div>

          {/* Animated XP count + floating XP bursts */}
          <div className="relative text-xs text-nxt-muted">
            <span className="font-medium text-nxt-gold">
              <CountUp value={currentXp} duration={1200} />
            </span>{' '}
            XP
            <AnimatePresence>
              {bursts.map((b) => (
                <motion.span
                  key={b.id}
                  initial={{ y: 0, opacity: 0 }}
                  animate={
                    reduce
                      ? { y: -20, opacity: 0 }
                      : { y: -40, opacity: [0, 1, 1, 0] }
                  }
                  transition={{ duration: 1.5, ease: 'easeOut', times: [0, 0.1, 0.7, 1] }}
                  className="absolute -top-2 right-0 text-nxt-gold font-semibold text-xs pointer-events-none"
                >
                  +{b.value} XP
                </motion.span>
              ))}
            </AnimatePresence>
          </div>

          <div
            className="flex items-center gap-1 text-xs text-nxt-muted"
            title={`Best streak: ${profile.longest_streak ?? 0}`}
          >
            <span>🔥</span>
            <span>{profile.current_streak ?? 0}</span>
          </div>

          {onToggleSound && (
            <button
              type="button"
              onClick={onToggleSound}
              aria-label="Toggle sound"
              className="w-8 h-8 rounded-full hover:bg-nxt-panel grid place-items-center text-nxt-text/80"
              title={soundOn ? 'Sound on' : 'Sound off'}
            >
              {soundOn ? '🔊' : '🔇'}
            </button>
          )}

          <button
            type="button"
            aria-label="Notifications"
            className="w-8 h-8 rounded-full hover:bg-nxt-panel grid place-items-center text-nxt-text/80"
          >
            🔔
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="text-xs text-nxt-muted hover:text-nxt-accent"
          >
            Sign out
          </button>
        </>
      )}
    </header>
  );
}
