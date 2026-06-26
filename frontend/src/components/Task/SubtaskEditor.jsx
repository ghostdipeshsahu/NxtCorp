import { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

// Type 1 — Decompose.
//
// Priya hands the student a vague problem. The student must produce a list
// of precise sub-tasks the spec needs to cover. Backend judges coverage
// against question.expected_subtasks via the LLM judge.
//
// Input: one sub-task per non-empty line in the textarea.
// Sends: { subtasks: [str, ...] }.

export default function SubtaskEditor({
  task,
  onRun,
  running,
  attemptNumber,
  disabled,
}) {
  const reduce = useReducedMotion();
  const [text, setText] = useState('');
  const expectedCount = task?.expected_subtasks_count;

  function submit(e) {
    e.preventDefault();
    const subtasks = text
      .split(/\r?\n/)
      .map((line) => line.replace(/^[\s\-*•\d.]+/, '').trim())
      .filter(Boolean);
    if (!subtasks.length) return;
    onRun({ subtasks });
  }

  const lineCount = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean).length;

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="rounded-xl border border-nxt-lamp/40 bg-nxt-lamp/10 px-3 py-2 text-xs text-nxt-text/85">
        <span className="font-medium text-nxt-lamp">Type 2 · Decompose Vague Work</span>
        <div className="text-nxt-muted mt-0.5">
          The requirement from the meeting was vague. Before writing any
          instructions to AI, break it down into precise parts. Think about:
          what goes in, what comes out, what rules apply, and what could go
          wrong. One sub-task per line.
          {typeof expectedCount === 'number' && (
            <span> Aim for around <span className="text-nxt-text">{expectedCount}</span>.</span>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <label className="text-xs uppercase tracking-wider text-nxt-muted">
          Sub-tasks (one per line)
        </label>
        <div className="text-[10px] text-nxt-muted">Attempt #{attemptNumber}</div>
      </div>

      <textarea
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled || running}
        placeholder={`e.g.\n- State the function name and parameters\n- Cover the all-uppercase rule\n- Cover single-character inputs`}
        className="w-full rounded-xl border border-nxt-border bg-nxt-panel/60 text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm focus:outline-none focus:border-nxt-accent focus:ring-2 focus:ring-nxt-accent/30 resize-none disabled:opacity-60"
      />

      <div className="flex items-center justify-between">
        <div className="text-[11px] text-nxt-muted">
          {lineCount} sub-task{lineCount === 1 ? '' : 's'}
        </div>
        <motion.button
          type="submit"
          disabled={running || disabled || !lineCount}
          whileHover={reduce ? undefined : { scale: 1.02 }}
          whileTap={reduce ? undefined : { scale: 0.96 }}
          className="rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 transition shadow-panel"
        >
          {running ? 'Checking…' : 'Submit decomposition ▶'}
        </motion.button>
      </div>
    </form>
  );
}
