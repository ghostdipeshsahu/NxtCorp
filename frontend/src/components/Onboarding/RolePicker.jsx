import { useState } from 'react';

// v3 onboarding step. The job role personalizes the kinds of tasks the
// Client Task Agent generates — e.g. data analysts see dataframe-shaped
// problems, DevOps engineers see config / scripting problems, etc.
export const JOB_ROLES = [
  {
    key: 'software_developer',
    label: 'Software Developer',
    blurb: 'Web, backend, mobile — general application code.',
    icon: '💻',
  },
  {
    key: 'data_analyst',
    label: 'Data Analyst',
    blurb: 'Pulling, shaping, and validating data for the business.',
    icon: '📊',
  },
  {
    key: 'genai_engineer',
    label: 'GenAI Engineer',
    blurb: 'Building LLM-powered features: prompts, pipelines, evals.',
    icon: '🤖',
  },
  {
    key: 'qa_engineer',
    label: 'QA Engineer',
    blurb: 'Catching bugs before they ship — tests, automation, reviews.',
    icon: '🔍',
  },
  {
    key: 'devops_engineer',
    label: 'DevOps Engineer',
    blurb: 'Infra, deploys, scripts that keep the lights on.',
    icon: '⚙️',
  },
];

export default function RolePicker({ initial = 'software_developer', onBack, onNext }) {
  const [selected, setSelected] = useState(
    JOB_ROLES.some((r) => r.key === initial) ? initial : 'software_developer',
  );

  return (
    <div>
      <h2 className="font-display text-2xl text-nxt-text mb-1">Pick your role</h2>
      <p className="text-nxt-muted text-sm mb-5">
        Which seat are you taking at NxtCorp? This shapes the kinds of tickets you'll work on.
      </p>

      <div className="grid grid-cols-1 gap-2 mb-6">
        {JOB_ROLES.map((r) => {
          const isSel = r.key === selected;
          return (
            <button
              key={r.key}
              type="button"
              onClick={() => setSelected(r.key)}
              className={
                'flex items-start gap-3 p-3 rounded-xl border text-left transition ' +
                (isSel
                  ? 'border-nxt-accent bg-nxt-accent/10 ring-2 ring-nxt-accent/40'
                  : 'border-nxt-border hover:border-nxt-muted')
              }
              aria-pressed={isSel}
              aria-label={r.label}
            >
              <div className="text-2xl leading-none">{r.icon}</div>
              <div className="flex-1">
                <div className={'text-sm font-medium ' + (isSel ? 'text-nxt-gold' : 'text-nxt-text')}>
                  {r.label}
                </div>
                <div className="text-[11px] text-nxt-muted leading-snug mt-0.5">
                  {r.blurb}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onBack}
          className="flex-1 rounded-lg border border-nxt-border hover:bg-nxt-panel text-nxt-text/80 py-2 transition"
        >
          ← Back
        </button>
        <button
          type="button"
          onClick={() => onNext(selected)}
          className="flex-1 rounded-lg bg-nxt-accent hover:brightness-110 text-white font-medium py-2 transition"
        >
          Continue →
        </button>
      </div>
    </div>
  );
}
