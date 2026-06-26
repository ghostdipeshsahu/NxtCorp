import { Suspense, lazy } from 'react';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';
import Characters from './Characters.jsx';

// Lazy-load the Three.js scene so the React UI is interactive before the
// office canvas finishes mounting (spec §7 performance requirement).
const ThreeOffice = lazy(() => import('./ThreeOffice.jsx'));

export default function OfficeView({ profile, priyaExpression = 'neutral' }) {
  return (
    <div className="relative h-full rounded-2xl overflow-hidden border border-nxt-border shadow-panel">
      {/* Three.js background — fills the panel */}
      <div className="absolute inset-0">
        <Suspense fallback={<div className="w-full h-full bg-nxt-bg" />}>
          <ThreeOffice />
        </Suspense>
      </div>

      {/* DOM overlay: floor label */}
      <div className="absolute top-3 right-4 text-[10px] uppercase tracking-wider text-nxt-muted pointer-events-none">
        NxtCorp · Hyderabad Office
      </div>

      {/* Characters layer */}
      <Characters priyaExpression={priyaExpression} />

      {/* Player desk callout */}
      <div className="absolute left-3 bottom-3 flex items-center gap-2 px-2 py-2 rounded-xl bg-nxt-surface/85 border border-nxt-border backdrop-blur shadow-panel">
        <CharacterAvatar
          character="player"
          avatarId={profile?.avatar_id || 'avatar_02'}
          expression="thinking"
          size={36}
        />
        <div className="leading-tight">
          <div className="text-[10px] uppercase tracking-wider text-nxt-muted">Your desk</div>
          <div className="text-sm text-nxt-text font-medium">{profile?.display_name || 'Junior dev'}</div>
          <div className="text-[10px] text-nxt-accent">{profile?.job_title || 'AI Trainee'}</div>
        </div>
      </div>
    </div>
  );
}
