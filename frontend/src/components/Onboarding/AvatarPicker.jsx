import { useState } from 'react';
import CharacterAvatar, {
  PLAYER_AVATARS,
  PLAYER_AVATAR_IDS,
} from '../Chat/CharacterAvatar.jsx';

export default function AvatarPicker({ initial = 'avatar_02', onBack, onNext }) {
  const [selected, setSelected] = useState(
    PLAYER_AVATAR_IDS.includes(initial) ? initial : 'avatar_02',
  );

  return (
    <div>
      <h2 className="font-display text-2xl text-nxt-text mb-1">Pick your avatar</h2>
      <p className="text-nxt-muted text-sm mb-5">
        Shows up in chat and at your desk. You can change it later in settings.
      </p>

      <div className="grid grid-cols-5 gap-3 mb-6">
        {PLAYER_AVATAR_IDS.map((id) => {
          const isSel = id === selected;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setSelected(id)}
              className={
                'flex flex-col items-center gap-1 p-2 rounded-xl border transition ' +
                (isSel
                  ? 'border-nxt-accent bg-nxt-accent/10 ring-2 ring-nxt-accent/40'
                  : 'border-nxt-border hover:border-nxt-muted')
              }
              aria-pressed={isSel}
              aria-label={PLAYER_AVATARS[id].name}
            >
              <CharacterAvatar character="player" avatarId={id} expression="happy" size={56} />
              <span className={'text-[10px] ' + (isSel ? 'text-nxt-gold font-medium' : 'text-nxt-muted')}>
                {PLAYER_AVATARS[id].name}
              </span>
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
