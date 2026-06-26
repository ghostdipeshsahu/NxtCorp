import { motion, useReducedMotion } from 'framer-motion';
import CharacterAvatar, { characterMeta } from './CharacterAvatar.jsx';
import Typewriter from '../UI/Typewriter.jsx';

export default function Message({ message, playerName = 'You', playerAvatarId = 'avatar_02' }) {
  const reduce = useReducedMotion();
  const isPlayer = message.character === 'player';
  const meta = characterMeta(message.character, playerAvatarId);
  const name = isPlayer ? playerName : meta.label;

  const initial = reduce ? false : { opacity: 0, x: isPlayer ? 20 : -20 };
  const animate = { opacity: 1, x: 0 };

  // Typewriter only for newly-arrived coach messages. Skip when reduce-motion.
  // Skip framing messages (id === 'framing') and Day-1 prefab so they appear
  // instantly on first paint.
  const shouldType =
    !reduce &&
    !isPlayer &&
    !String(message.id || '').startsWith('framing') &&
    !String(message.id || '').startsWith('day1_') &&
    !!message.body;

  return (
    <motion.div
      initial={initial}
      animate={animate}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={'flex gap-2 ' + (isPlayer ? 'flex-row-reverse' : '')}
    >
      <CharacterAvatar
        character={message.character}
        avatarId={playerAvatarId}
        expression={message.expression || 'neutral'}
        size={36}
      />
      <div className={'max-w-[85%] ' + (isPlayer ? 'items-end text-right' : 'items-start')}>
        <div className="text-[10px] uppercase tracking-wider text-nxt-muted mb-0.5">
          {name}
          {!isPlayer && meta.role ? (
            <span className="ml-1 text-nxt-muted/60">· {meta.role}</span>
          ) : null}
        </div>
        <div
          className={
            'inline-block px-3 py-2 rounded-2xl text-sm shadow-panel whitespace-pre-wrap text-left ' +
            (isPlayer
              ? 'bg-nxt-accent text-white rounded-tr-sm'
              : 'bg-nxt-panel text-nxt-text border border-nxt-border rounded-tl-sm')
          }
        >
          {shouldType ? <Typewriter text={message.body} charDelay={18} /> : message.body}
        </div>
        {message.escalation_level != null && message.escalation_level > 0 && (
          <div className="text-[10px] text-nxt-muted mt-1">
            Coaching level {message.escalation_level}
          </div>
        )}
      </div>
    </motion.div>
  );
}
