import { useState } from 'react';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';
import {
  ARJUN_INTRO,
  PRIYA_WELCOME,
  RAVI_INTRO,
  ZARA_INTRO,
} from '../../content/day1.js';

function StoryCard({ character, expression, name, role, body }) {
  return (
    <div className="flex gap-3 bg-nxt-panel/60 border border-nxt-border rounded-xl p-3 shadow-panel">
      <CharacterAvatar character={character} expression={expression} size={48} />
      <div className="flex-1 min-w-0">
        <div className="text-xs text-nxt-muted mb-0.5">
          <span className="font-medium text-nxt-text">{name}</span>
          <span className="text-nxt-muted/60"> · {role}</span>
        </div>
        <p className="text-sm text-nxt-text/90 whitespace-pre-wrap leading-relaxed">{body}</p>
      </div>
    </div>
  );
}

// v3: Day 1 introductions play in strict sequence.
//   step 0 → Priya welcome                  (Next → step 1)
//   step 1 → + Arjun introduces himself     (Next → step 2)
//   step 2 → + Zara's QA notice             (Next → step 3)
//   step 3 → + Ravi Sir's brief appearance  ("Go to my desk →")
export default function Day1Story({ displayName, avatarId, pronouns, busy, onBack, onSubmit }) {
  const [step, setStep] = useState(0);

  function handleBack() {
    if (step > 0) {
      setStep(step - 1);
      return;
    }
    onBack?.();
  }

  const subtitles = [
    `A message just landed for you, ${displayName}.`,
    'Another teammate dropped in to say hi.',
    'QA wants a word.',
    "And then there's Ravi Sir.",
  ];

  const lastStep = subtitles.length - 1;

  return (
    <div>
      <h2 className="font-display text-2xl text-nxt-text mb-1">Day 1 — meet the team</h2>
      <p className="text-nxt-muted text-sm mb-5">{subtitles[step] || subtitles[lastStep]}</p>

      <div className="space-y-3 mb-6">
        <StoryCard
          character="priya"
          expression="happy"
          name="Priya Sharma"
          role="Manager"
          body={PRIYA_WELCOME}
        />
        {step >= 1 && (
          <StoryCard
            character="arjun"
            expression="happy"
            name="Arjun Mehta"
            role="Senior Developer"
            body={ARJUN_INTRO}
          />
        )}
        {step >= 2 && (
          <StoryCard
            character="zara"
            expression="neutral"
            name="Zara Khan"
            role="QA Engineer"
            body={ZARA_INTRO}
          />
        )}
        {step >= 3 && (
          <StoryCard
            character="ravi"
            expression="proud"
            name="Ravi Sir"
            role="CTO"
            body={RAVI_INTRO}
          />
        )}
      </div>

      <div className="flex items-center gap-3 px-3 py-2 bg-nxt-panel/50 border border-nxt-border rounded-xl mb-4">
        <CharacterAvatar character="player" avatarId={avatarId} expression="excited" size={40} />
        <div className="text-xs text-nxt-muted">
          You · <span className="text-nxt-text">{displayName}</span>
          {pronouns ? <span className="text-nxt-muted/60"> · {pronouns}</span> : null}
          <div className="text-[10px] text-nxt-accent mt-0.5">AI Trainee</div>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleBack}
          disabled={busy}
          className="flex-1 rounded-lg border border-nxt-border hover:bg-nxt-panel text-nxt-text/80 py-2 transition disabled:opacity-50"
        >
          ← Back
        </button>
        {step < lastStep ? (
          <button
            type="button"
            onClick={() => setStep(step + 1)}
            className="flex-1 rounded-lg bg-nxt-accent hover:brightness-110 text-white font-medium py-2 transition shadow-panel"
          >
            Next →
          </button>
        ) : (
          <button
            type="button"
            onClick={onSubmit}
            disabled={busy}
            className="flex-1 rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-50 text-white font-medium py-2 transition shadow-panel"
          >
            {busy ? 'Heading to your desk…' : 'Go to my desk →'}
          </button>
        )}
      </div>
    </div>
  );
}
