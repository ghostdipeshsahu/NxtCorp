import { useEffect, useState } from 'react';
import CharacterAvatar, { characterMeta } from '../Chat/CharacterAvatar.jsx';

// Renders a single story event as a sequence of messages. Tap Continue to
// reveal the next message; on the final tap, calls onContinue (advance with
// XP). Skip dismisses without XP (spec §4: "Student can skip story events
// (but misses XP bonuses)").
export default function StoryEventOverlay({ event, onContinue, onSkip, busy }) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    // Reset whenever a new event arrives.
    setIndex(0);
  }, [event?.event_key]);

  if (!event) return null;
  const messages = event.messages || [];
  const isLast = index >= messages.length - 1;

  function advanceOrFinish() {
    if (isLast) {
      onContinue();
    } else {
      setIndex((i) => i + 1);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/65 backdrop-blur grid place-items-center p-6 z-50"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-lg bg-nxt-surface rounded-2xl shadow-panel border border-nxt-border p-6 text-nxt-text">
        <div className="flex items-baseline justify-between mb-3">
          <div className="text-xs uppercase tracking-wider text-nxt-muted">
            Story moment
            {event.story_day != null && <span className="ml-1">· Day {event.story_day}</span>}
          </div>
          <div className="text-[10px] text-nxt-muted">
            {index + 1} / {messages.length}
          </div>
        </div>

        <h2 className="font-display text-lg text-nxt-text mb-4">{event.title}</h2>

        <div className="space-y-3 mb-5 max-h-96 overflow-y-auto">
          {messages.slice(0, index + 1).map((m, i) => {
            const meta = characterMeta(m.character);
            return (
              <div key={i} className="flex gap-2 items-start">
                <CharacterAvatar
                  character={m.character}
                  expression={m.expression}
                  size={40}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] uppercase tracking-wider text-nxt-muted mb-0.5">
                    <span className="text-nxt-text font-medium">{meta.label}</span>
                    {meta.role && <span className="text-nxt-muted/60"> · {meta.role}</span>}
                  </div>
                  <div className="text-sm text-nxt-text whitespace-pre-wrap bg-nxt-panel border border-nxt-border rounded-2xl rounded-tl-sm px-3 py-2 leading-relaxed">
                    {m.body}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSkip}
            disabled={busy}
            className="text-xs text-nxt-muted hover:text-nxt-text px-3 py-2 disabled:opacity-50"
          >
            Skip (no XP)
          </button>
          <div className="flex-1" />
          <div className="text-[10px] text-nxt-gold">+{event.xp_bonus} XP</div>
          <button
            type="button"
            onClick={advanceOrFinish}
            disabled={busy}
            className="rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-50 text-white font-medium text-sm px-4 py-2 transition"
          >
            {isLast ? (busy ? '…' : 'Continue →') : 'Next ›'}
          </button>
        </div>
      </div>
    </div>
  );
}
