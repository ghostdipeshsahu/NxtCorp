import { useState } from 'react';

export default function NamePicker({ initial = '', onBack, onNext }) {
  const [name, setName] = useState(initial);
  const trimmed = name.trim();

  function submit(e) {
    e.preventDefault();
    if (!trimmed) return;
    onNext(trimmed);
  }

  return (
    <form onSubmit={submit}>
      <h2 className="font-display text-2xl text-nxt-text mb-1">What should we call you?</h2>
      <p className="text-nxt-muted text-sm mb-5">
        First name is fine. Priya and the team will use this.
      </p>

      <input
        autoFocus
        className="w-full rounded-lg bg-nxt-panel border border-nxt-border text-nxt-text placeholder-nxt-muted px-3 py-2 text-base focus:outline-none focus:border-nxt-accent"
        placeholder="e.g. Aarav"
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={64}
      />

      <div className="flex gap-2 mt-6">
        <button
          type="button"
          onClick={onBack}
          className="flex-1 rounded-lg border border-nxt-border hover:bg-nxt-panel text-nxt-text/80 py-2 transition"
        >
          ← Back
        </button>
        <button
          type="submit"
          disabled={!trimmed}
          className="flex-1 rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium py-2 transition"
        >
          Continue →
        </button>
      </div>
    </form>
  );
}
