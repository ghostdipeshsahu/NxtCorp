import { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

// Type 2 — Spot the Gap.
//
// Arjun shows the student a flawed_prompt he wrote. The student must
// enumerate what's missing or wrong. Backend judges coverage against
// question.expected_gaps via the LLM judge.
//
// Input: one gap per non-empty line.
// Sends: { identified_gaps: [str, ...] }.

export default function GapEditor({
  task,
  onRun,
  running,
  attemptNumber,
  disabled,
}) {
  const reduce = useReducedMotion();
  const [text, setText] = useState('');
  const flawed = task?.flawed_prompt || '';
  const expectedCount = task?.expected_gaps_count;

  function submit(e) {
    e.preventDefault();
    const gaps = text
      .split(/\r?\n/)
      .map((line) => line.replace(/^[\s\-*•\d.]+/, '').trim())
      .filter(Boolean);
    if (!gaps.length) return;
    onRun({ identified_gaps: gaps });
  }

  const lineCount = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean).length;

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="rounded-xl border border-nxt-lamp/40 bg-nxt-lamp/10 px-3 py-2 text-xs text-nxt-text/85">
        <span className="font-medium text-nxt-lamp">Type 3 · Predict AI Failure</span>
        <div className="text-nxt-muted mt-0.5">
          The team built this using AI. Before it ships, find every case
          where it might give the wrong answer. Think about the rules from
          the meeting — where did the original prompt leave gaps? Be
          specific: name the exact input and what goes wrong.
          {typeof expectedCount === 'number' && (
            <span> Aim for around <span className="text-nxt-text">{expectedCount}</span>.</span>
          )}
        </div>
      </div>

      {/* Arjun's flawed prompt */}
      <div className="rounded-xl border border-nxt-border bg-nxt-panel/60 p-3">
        <div className="text-[10px] uppercase tracking-wider text-nxt-muted mb-1">
          🤔 Arjun's draft prompt — review it
        </div>
        <div className="text-sm text-nxt-text/95 whitespace-pre-wrap leading-relaxed">
          {flawed || '(no flawed_prompt provided)'}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <label className="text-xs uppercase tracking-wider text-nxt-muted">
          Gaps you found (one per line)
        </label>
        <div className="text-[10px] text-nxt-muted">Attempt #{attemptNumber}</div>
      </div>

      <textarea
        rows={6}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled || running}
        placeholder={`e.g.\n- Doesn't say what to return for all-lowercase words\n- Doesn't specify return type\n- Doesn't handle single-character inputs`}
        className="w-full rounded-xl border border-nxt-border bg-nxt-panel/60 text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm focus:outline-none focus:border-nxt-accent focus:ring-2 focus:ring-nxt-accent/30 resize-none disabled:opacity-60"
      />

      <div className="flex items-center justify-between">
        <div className="text-[11px] text-nxt-muted">
          {lineCount} gap{lineCount === 1 ? '' : 's'} listed
        </div>
        <motion.button
          type="submit"
          disabled={running || disabled || !lineCount}
          whileHover={reduce ? undefined : { scale: 1.02 }}
          whileTap={reduce ? undefined : { scale: 0.96 }}
          className="rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 transition shadow-panel"
        >
          {running ? 'Checking…' : 'Submit gaps ▶'}
        </motion.button>
      </div>
    </form>
  );
}
