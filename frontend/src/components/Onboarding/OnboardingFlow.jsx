import { useState } from 'react';
import WelcomeScreen from './WelcomeScreen.jsx';
import NamePicker from './NamePicker.jsx';
import AvatarPicker from './AvatarPicker.jsx';
import RolePicker from './RolePicker.jsx';
import Day1Story from './Day1Story.jsx';

// v3: pronouns step removed. Backend still accepts the field (null) but no
// player input is collected. Role step is new.
const STEPS = ['welcome', 'name', 'avatar', 'role', 'day1'];

function StepDots({ index, total }) {
  return (
    <div className="flex items-center justify-center gap-1.5 mt-4">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={
            'h-1.5 rounded-full transition-all ' +
            (i <= index ? 'w-6 bg-nxt-accent' : 'w-1.5 bg-nxt-border')
          }
        />
      ))}
    </div>
  );
}

export default function OnboardingFlow({ initialProfile, onComplete, onSubmit }) {
  const [step, setStep] = useState(0);
  const [displayName, setDisplayName] = useState(
    initialProfile?.display_name && initialProfile.display_name !== initialProfile.username
      ? initialProfile.display_name
      : '',
  );
  const [avatarId, setAvatarId] = useState(initialProfile?.avatar_id || 'avatar_02');
  const [jobRole, setJobRole] = useState(initialProfile?.job_role || 'software_developer');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const name = STEPS[step];

  function back() {
    setStep((s) => Math.max(0, s - 1));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        display_name: displayName,
        avatar_id: avatarId,
        pronouns: null,
        job_role: jobRole,
      });
      onComplete();
    } catch (e) {
      setError(e.message || 'Could not finish onboarding.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full max-h-screen overflow-y-auto flex items-start sm:items-center justify-center bg-nxt-bg p-6">
      <div
        className="onb-no-select w-full max-w-md my-auto bg-nxt-surface border border-nxt-border rounded-2xl shadow-panel p-8 text-nxt-text"
      >
        {name === 'welcome' && (
          <WelcomeScreen
            username={initialProfile?.username}
            onNext={() => setStep(1)}
          />
        )}
        {name === 'name' && (
          <NamePicker
            initial={displayName}
            onBack={back}
            onNext={(v) => {
              setDisplayName(v);
              setStep(2);
            }}
          />
        )}
        {name === 'avatar' && (
          <AvatarPicker
            initial={avatarId}
            onBack={back}
            onNext={(v) => {
              setAvatarId(v);
              setStep(3);
            }}
          />
        )}
        {name === 'role' && (
          <RolePicker
            initial={jobRole}
            onBack={back}
            onNext={(v) => {
              setJobRole(v);
              setStep(4);
            }}
          />
        )}
        {name === 'day1' && (
          <Day1Story
            displayName={displayName}
            avatarId={avatarId}
            pronouns={null}
            jobRole={jobRole}
            busy={busy}
            onBack={back}
            onSubmit={submit}
          />
        )}

        {error && (
          <div className="mt-3 text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <StepDots index={step} total={STEPS.length} />
      </div>
    </div>
  );
}
