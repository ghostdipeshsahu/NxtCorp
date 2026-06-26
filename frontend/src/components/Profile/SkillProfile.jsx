import { motion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';
import { JOB_LEVEL_TOOLTIPS } from '../../content/levels.js';

const SKILL_LABELS = {
  decomposition: 'Problem Decomposition',
  edge_case: 'Edge Case Thinking',
  requirement_completeness: 'Requirement Completeness',
  output_verification: 'Output Verification',
  iterative_refinement: 'Iterative Refinement',
  prompt_optimization: 'Prompt Optimization',
};

// Canonical definitions for the 6 AI-supervision skills (v3 spec).
// These show in the profile tooltip and frame what each skill means
// when supervising AI rather than writing code yourself.
const SKILL_DEFINITIONS = {
  decomposition:
    'Converting stakeholder requirements into precise AI-executable sub-tasks.',
  edge_case:
    'Predicting where AI will fail because the instructions left gaps.',
  requirement_completeness:
    'Writing AI instructions complete enough that nothing important is left for AI to assume.',
  output_verification:
    'Checking AI output against what stakeholders actually asked for.',
  iterative_refinement:
    'Fixing AI instructions precisely based on what the failure reveals.',
  prompt_optimization:
    'Pushing AI output from "working" to "excellent" — performance, readability, idiomatic style — by adjusting the prompt rather than the code.',
};

const LOCKED_SKILLS = new Set(['prompt_optimization']);
const LOCKED_TOOLTIP =
  "Phase 4 — Prompt Optimization (Coming Soon). You have learned to gather requirements, use AI to build features, and verify the output. Phase 4 teaches you to push working AI output from correct to production quality — faster, cleaner, and more reliable.";

const BADGE_LABELS = {
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

function SkillRow({ skill, index }) {
  const label = SKILL_LABELS[skill.skill] || skill.skill;
  const definition = SKILL_DEFINITIONS[skill.skill] || '';
  const pct = ((skill.score ?? 0) / 10) * 100;
  const locked = LOCKED_SKILLS.has(skill.skill);

  if (locked) {
    return (
      <div className="opacity-60" title={`${definition}\n\n${LOCKED_TOOLTIP}`}>
        <div className="flex items-baseline justify-between mb-1">
          <div className="text-sm text-nxt-text flex items-center gap-1.5">
            <span>🔒</span>
            <span className="border-b border-dotted border-nxt-muted/50 cursor-help">{label}</span>
          </div>
          <div className="text-xs text-nxt-muted">
            <span className="mr-2">Phase 4</span>
            <span className="font-mono">— / 10</span>
          </div>
        </div>
        <div className="w-full h-2 rounded-full bg-nxt-panel overflow-hidden" />
      </div>
    );
  }

  return (
    <div title={definition}>
      <div className="flex items-baseline justify-between mb-1">
        <div className="text-sm text-nxt-text border-b border-dotted border-nxt-muted/40 cursor-help inline-block">
          {label}
        </div>
        <div className="text-xs text-nxt-muted">
          <span className="mr-2">{skill.tier}</span>
          <span className="font-mono">{(skill.score ?? 0).toFixed(1)} / 10</span>
        </div>
      </div>
      <div className="w-full h-2 rounded-full bg-nxt-panel overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-nxt-accent to-nxt-gold"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, delay: index * 0.15, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}

function BadgeChip({ badgeKey, earnedAt, index }) {
  const meta = BADGE_LABELS[badgeKey] || { label: badgeKey, icon: '✨', blurb: '' };
  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.35, delay: index * 0.1, type: 'spring', stiffness: 250, damping: 18 }}
      className="flex items-center gap-2 bg-nxt-panel/70 border border-nxt-border rounded-xl px-2.5 py-1.5 shadow-panel"
      title={meta.blurb}
    >
      <span className="text-base leading-none">{meta.icon}</span>
      <div className="leading-tight">
        <div className="text-xs font-medium text-nxt-text">{meta.label}</div>
        {earnedAt && (
          <div className="text-[10px] text-nxt-muted">
            {new Date(earnedAt).toLocaleDateString()}
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default function SkillProfile({ profile }) {
  if (!profile) return null;
  const skills = profile.skills || [];
  const badges = profile.badges || [];
  const xpProgress = profile.progress_to_next_level ?? 0;

  return (
    <div className="bg-nxt-surface border border-nxt-border rounded-2xl shadow-panel p-5 w-full max-w-md text-nxt-text">
      <div className="flex items-center gap-3 mb-4">
        <CharacterAvatar
          character="player"
          avatarId={profile.avatar_id}
          expression="happy"
          size={56}
        />
        <div className="leading-tight">
          <div className="font-display text-lg text-nxt-text flex items-center gap-2">
            {profile.display_name}
            <span
              className="px-1.5 py-0.5 rounded text-[9px] uppercase tracking-wider font-sans bg-nxt-panel border border-nxt-border text-nxt-muted"
              title="Current learning phase"
            >
              Phase {profile.progression_phase ?? '1'}
            </span>
          </div>
          <div
            className="text-xs text-nxt-accent cursor-help"
            title={JOB_LEVEL_TOOLTIPS[profile.job_level] || ''}
          >
            {profile.job_title}
          </div>
          <div className="text-[10px] text-nxt-muted">
            @{profile.username}
            {profile.pronouns ? <span> · {profile.pronouns}</span> : null}
          </div>
        </div>
      </div>

      <div className="mb-5">
        <div className="flex items-baseline justify-between mb-1">
          <div className="text-xs uppercase tracking-wider text-nxt-muted">
            Level {profile.job_level}
          </div>
          <div
            className="text-[11px] text-nxt-muted cursor-help"
            title={JOB_LEVEL_TOOLTIPS[(profile.job_level || 0) + 1] || ''}
          >
            {profile.next_level_title ? (
              <>
                {(xpProgress * 100).toFixed(0)}% to {profile.next_level_title}
              </>
            ) : (
              <>Max level reached</>
            )}
          </div>
        </div>
        <div className="w-full h-2.5 rounded-full bg-nxt-panel overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-nxt-accent to-nxt-gold"
            initial={{ width: 0 }}
            animate={{ width: `${xpProgress * 100}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-5 text-center">
        <div className="rounded-xl bg-nxt-panel/60 border border-nxt-border p-2">
          <div className="text-[10px] uppercase tracking-wider text-nxt-muted">Total XP</div>
          <div className="text-base font-medium text-nxt-gold">{profile.total_xp ?? 0}</div>
        </div>
        <div className="rounded-xl bg-nxt-panel/60 border border-nxt-border p-2">
          <div className="text-[10px] uppercase tracking-wider text-nxt-muted">Overall</div>
          <div className="text-base font-medium text-nxt-text">
            {(profile.overall_skill_score ?? 0).toFixed(1)}/10
          </div>
        </div>
        <div className="rounded-xl bg-nxt-panel/60 border border-nxt-border p-2">
          <div className="text-[10px] uppercase tracking-wider text-nxt-muted">Streak</div>
          <div className="text-base font-medium text-nxt-text">
            🔥 {profile.current_streak ?? 0}
            <span className="text-[10px] text-nxt-muted ml-1">best {profile.longest_streak ?? 0}</span>
          </div>
        </div>
      </div>

      <div className="mb-5">
        <div className="text-xs uppercase tracking-wider text-nxt-muted mb-2">Skills</div>
        <div className="space-y-2.5">
          {skills.map((s, i) => (
            <SkillRow key={s.skill} skill={s} index={i} />
          ))}
        </div>
      </div>

      <div>
        <div className="text-xs uppercase tracking-wider text-nxt-muted mb-2">
          Badges {badges.length > 0 && <span className="text-nxt-muted/60">· {badges.length}</span>}
        </div>
        {badges.length === 0 ? (
          <div className="text-xs text-nxt-muted italic">No badges yet. Pass a ticket to start.</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {badges.map((b, i) => (
              <BadgeChip key={b.badge_key} badgeKey={b.badge_key} earnedAt={b.earned_at} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
