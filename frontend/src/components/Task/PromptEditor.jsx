import { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

export default function PromptEditor({ onRun, running, attemptNumber, disabled }) {
  const [prompt, setPrompt] = useState('');
  const reduce = useReducedMotion();

  function submit(e) {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed) return;
    // App.handleRun expects an object payload keyed by the active type.
    onRun({ student_prompt: trimmed });
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs uppercase tracking-wider text-nxt-muted">
          Your instructions to the AI
        </label>
        <div className="text-[10px] text-nxt-muted">Attempt #{attemptNumber}</div>
      </div>
      <motion.div
        animate={
          running && !reduce
            ? {
                boxShadow: [
                  '0 0 0 0 rgba(233,69,96,0)',
                  '0 0 28px 6px rgba(233,69,96,0.35)',
                  '0 0 0 0 rgba(233,69,96,0)',
                ],
              }
            : { boxShadow: '0 0 0 0 rgba(233,69,96,0)' }
        }
        transition={{ duration: 1.6, repeat: running ? Infinity : 0, ease: 'easeInOut' }}
        className="rounded-xl"
      >
        <textarea
          rows={8}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={disabled || running}
          placeholder="You attended the meeting and took notes. Now write precise instructions to AI to build exactly what the stakeholders asked for. Every rule they mentioned must be in your instructions — AI only knows what you tell it."
          className="w-full rounded-xl border border-nxt-border bg-nxt-panel/60 text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm font-mono focus:outline-none focus:border-nxt-accent focus:ring-2 focus:ring-nxt-accent/30 resize-none disabled:opacity-60"
        />
      </motion.div>
      <div className="flex items-center justify-between">
        <div className="text-[11px] text-nxt-muted">
          {prompt.trim().length} chars · {prompt.trim().split(/\s+/).filter(Boolean).length} words
          {running && (
            <span className="ml-2 text-nxt-accent">
              · AI is writing code<span className="inline-block animate-pulse">…</span>
            </span>
          )}
        </div>
        <motion.button
          type="submit"
          disabled={running || disabled || !prompt.trim()}
          whileHover={reduce ? undefined : { scale: 1.02 }}
          whileTap={reduce ? undefined : { scale: 0.96 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          className="rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 transition shadow-panel"
        >
          {running ? 'Running…' : 'Submit ticket ▶'}
        </motion.button>
      </div>
    </form>
  );
}
