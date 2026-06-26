import { useState } from 'react';

const OPTIONS = [
  { value: 'he/him', label: 'he / him' },
  { value: 'she/her', label: 'she / her' },
  { value: 'they/them', label: 'they / them' },
  { value: '', label: 'prefer not to say' },
];

export default function PronounsPicker({ initial = '', onBack, onNext }) {
  const [value, setValue] = useState(initial);
  const [custom, setCustom] = useState('');
  const [useCustom, setUseCustom] = useState(false);

  function submit() {
    if (useCustom) onNext(custom.trim());
    else onNext(value);
  }

  return (
    <div>
      <h2 className="font-display text-2xl text-nxt-text mb-1">Pronouns (optional)</h2>
      <p className="text-nxt-muted text-sm mb-5">Helps your team refer to you correctly.</p>

      <div className="space-y-2">
        {OPTIONS.map((opt) => {
          const isSel = !useCustom && value === opt.value;
          return (
            <button
              key={opt.label}
              type="button"
              onClick={() => {
                setValue(opt.value);
                setUseCustom(false);
              }}
              className={
                'w-full text-left px-3 py-2 rounded-lg border transition text-sm ' +
                (isSel
                  ? 'border-nxt-accent bg-nxt-accent/10 text-nxt-gold'
                  : 'border-nxt-border hover:border-nxt-muted text-nxt-text/80')
              }
            >
              {opt.label}
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setUseCustom(true)}
          className={
            'w-full text-left px-3 py-2 rounded-lg border transition text-sm ' +
            (useCustom
              ? 'border-nxt-accent bg-nxt-accent/10 text-nxt-gold'
              : 'border-nxt-border hover:border-nxt-muted text-nxt-text/80')
          }
        >
          custom…
        </button>
        {useCustom && (
          <input
            autoFocus
            className="w-full rounded-lg bg-nxt-panel border border-nxt-border text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm focus:outline-none focus:border-nxt-accent"
            placeholder="e.g. xe / xem"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            maxLength={32}
          />
        )}
      </div>

      <div className="flex gap-2 mt-6">
        <button
          type="button"
          onClick={onBack}
          className="flex-1 rounded-lg border border-nxt-border hover:bg-nxt-panel text-nxt-text/80 py-2 transition"
        >
          ← Back
        </button>
        <button
          type="button"
          onClick={submit}
          className="flex-1 rounded-lg bg-nxt-accent hover:brightness-110 text-white font-medium py-2 transition"
        >
          Continue →
        </button>
      </div>
    </div>
  );
}
