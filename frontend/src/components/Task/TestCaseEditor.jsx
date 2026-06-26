import { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

// Type 4 — Verify.
//
// Zara hands the student a chunk of generated code (`target_code`). The
// student must write test cases that would catch any bug. Backend:
//   - runs each case against reference_code to check the student's
//     `expected` is correct
//   - measures coverage of the question's hidden_tests (via input equality)
//
// Each line in the textarea is one test case in the form:
//     input | expected
// Both sides are parsed as JSON, with a string fallback. Examples:
//     "racecar" | true
//     [1, 2, 3] | [3, 2, 1]
//     50, 1.7 | "Underweight"
//
// Sends: { test_cases: [{input, expected}, ...] }.

function parseValue(raw) {
  const s = raw.trim();
  if (!s) return null;
  try {
    return JSON.parse(s);
  } catch (_) {
    // try comma-tuple => array
    if (s.includes(',')) {
      try {
        return JSON.parse('[' + s + ']');
      } catch (_) { /* fall through */ }
    }
    return s; // raw string fallback
  }
}

function parseCases(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const idx = line.indexOf('|');
      if (idx === -1) return null;
      const input = parseValue(line.slice(0, idx));
      const expected = parseValue(line.slice(idx + 1));
      if (input == null && expected == null) return null;
      return { input, expected };
    })
    .filter(Boolean);
}

export default function TestCaseEditor({
  task,
  onRun,
  running,
  attemptNumber,
  disabled,
}) {
  const reduce = useReducedMotion();
  const [text, setText] = useState('');
  const target = task?.target_code || '';

  const cases = parseCases(text);

  function submit(e) {
    e.preventDefault();
    if (!cases.length) return;
    onRun({ test_cases: cases });
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="rounded-xl border border-nxt-lamp/40 bg-nxt-lamp/10 px-3 py-2 text-xs text-nxt-text/85">
        <span className="font-medium text-nxt-lamp">Type 4 · Verify AI Output</span>
        <div className="text-nxt-muted mt-0.5">
          AI built this feature. Your job is to verify it actually does what
          the stakeholders asked for in the meeting. Write test cases —
          specific inputs with expected outputs — that would catch any bugs.
          Think about the rules from the meeting: is the code following all
          of them?
        </div>
      </div>

      {/* Target code (the implementation under test) */}
      <div className="rounded-xl border border-nxt-border bg-nxt-bg/80 p-3">
        <div className="text-[10px] uppercase tracking-wider text-nxt-muted mb-1">
          🔍 Code to verify
        </div>
        <pre className="text-xs font-mono text-nxt-text whitespace-pre overflow-x-auto leading-snug">
{target || '(no target_code provided)'}
        </pre>
      </div>

      <div className="flex items-center justify-between">
        <label className="text-xs uppercase tracking-wider text-nxt-muted">
          Test cases — one per line, format <span className="font-mono text-nxt-text">input | expected</span>
        </label>
        <div className="text-[10px] text-nxt-muted">Attempt #{attemptNumber}</div>
      </div>

      <textarea
        rows={6}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled || running}
        placeholder={`"racecar" | true\n"" | true\n[1,2,3], 2 | [2,3,1]\n50, 1.7 | "Underweight"`}
        className="w-full rounded-xl border border-nxt-border bg-nxt-panel/60 text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm font-mono focus:outline-none focus:border-nxt-accent focus:ring-2 focus:ring-nxt-accent/30 resize-none disabled:opacity-60"
      />

      <div className="flex items-center justify-between">
        <div className="text-[11px] text-nxt-muted">
          {cases.length} valid case{cases.length === 1 ? '' : 's'} parsed
        </div>
        <motion.button
          type="submit"
          disabled={running || disabled || !cases.length}
          whileHover={reduce ? undefined : { scale: 1.02 }}
          whileTap={reduce ? undefined : { scale: 0.96 }}
          className="rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 transition shadow-panel"
        >
          {running ? 'Running…' : 'Submit tests ▶'}
        </motion.button>
      </div>
    </form>
  );
}
