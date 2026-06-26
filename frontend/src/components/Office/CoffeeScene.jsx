import { useCallback, useEffect, useReducer } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';
import { getCharacterPortrait, getSceneBackground } from '../../assets/index.js';
import { postCoffeeTurn } from '../../api.js';

// v3 multi-turn coffee corner. Conversation script:
//   round 0 → fixed greeting from Arjun + R1 options
//   round 1 → casual reply + R2 options
//   round 2 → directional hint + static closing; "Head back to my desk →"
//
// Backend is stateless across turns — this component drives the flow by
// POSTing /api/coffee/turn with (round, choice). Transcript is local.

const initialState = {
  transcript: [],         // [{ from: 'arjun' | 'player', body: string }]
  options: [],            // string[] - current round's choices
  isFinal: false,         // true once the hint has been delivered
  loading: true,          // fetching next Arjun line
  error: null,            // string | null
  nextRound: 0,           // round to send with the next user pick
};

function reducer(state, action) {
  switch (action.type) {
    case 'fetch_start':
      return { ...state, loading: true, error: null };
    case 'arjun_msg':
      return {
        ...state,
        loading: false,
        transcript: [...state.transcript, { from: 'arjun', body: action.body }],
        options: action.options,
        isFinal: action.isFinal,
        nextRound: action.nextRound,
      };
    case 'player_pick':
      return {
        ...state,
        transcript: [...state.transcript, { from: 'player', body: action.choice }],
        options: [],
        loading: true,
      };
    case 'error':
      return { ...state, loading: false, error: action.message };
    case 'reset':
      return initialState;
    default:
      return state;
  }
}


function Bubble({ from, body, avatar, playerName }) {
  const isArjun = from === 'arjun';
  return (
    <div className={`flex gap-2 ${isArjun ? 'justify-start' : 'justify-end'}`}>
      {isArjun && (
        <CharacterAvatar character="arjun" expression="happy" size={28} />
      )}
      <div
        className={
          'max-w-[85%] px-3 py-2 rounded-2xl text-xs leading-snug shadow-panel ' +
          (isArjun
            ? 'rounded-bl-sm bg-black/65 backdrop-blur border border-nxt-lamp/40 text-white'
            : 'rounded-br-sm bg-nxt-accent/80 text-white')
        }
      >
        {!isArjun && playerName && (
          <div className="text-[9px] opacity-70 mb-0.5">{playerName}</div>
        )}
        <div className="whitespace-pre-wrap">{body}</div>
      </div>
      {!isArjun && avatar && (
        <CharacterAvatar character="player" avatarId={avatar} expression="happy" size={28} />
      )}
    </div>
  );
}


export default function CoffeeScene({ open = true, profile, onBack }) {
  const reduce = useReducedMotion();
  const bgUrl = getSceneBackground('coffee');
  const arjunPortrait = getCharacterPortrait('arjun', 'happy');

  const [state, dispatch] = useReducer(reducer, initialState);

  const fetchTurn = useCallback(async (round, choice) => {
    dispatch({ type: 'fetch_start' });
    try {
      const resp = await postCoffeeTurn({ round, choice });
      dispatch({
        type: 'arjun_msg',
        body: resp.arjun_message,
        options: resp.options || [],
        isFinal: !!resp.is_final,
        nextRound: round + 1,
      });
    } catch (err) {
      dispatch({
        type: 'error',
        message:
          err?.isNetwork
            ? "Can't reach the backend right now. Try again in a moment."
            : err?.message || 'Arjun got pulled away. Try again.',
      });
    }
  }, []);

  // Kick off round 0 when scene opens. Reset state if scene re-opens later.
  useEffect(() => {
    if (!open) return undefined;
    dispatch({ type: 'reset' });
    fetchTurn(0, null);
    return undefined;
  }, [open, fetchTurn]);

  function handlePick(choice) {
    dispatch({ type: 'player_pick', choice });
    fetchTurn(state.nextRound, choice);
  }

  // ---- shared interior render ----
  const transcript = (
    <div className="space-y-2">
      <AnimatePresence initial={false}>
        {state.transcript.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            <Bubble
              from={m.from}
              body={m.body}
              avatar={profile?.avatar_id}
              playerName={profile?.display_name}
            />
          </motion.div>
        ))}
        {state.loading && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="text-[10px] italic text-white/70 px-1"
          >
            Arjun is typing…
          </motion.div>
        )}
        {state.error && (
          <motion.div
            key="err"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="text-[11px] text-nxt-red px-2 py-1 rounded bg-red-500/10 border border-red-500/30"
          >
            {state.error}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );

  const controls = state.isFinal ? (
    <button
      type="button"
      onClick={onBack}
      className="w-full mt-3 rounded-lg bg-nxt-accent hover:brightness-110 text-white text-xs font-medium py-2 shadow-panel"
    >
      Head back to my desk →
    </button>
  ) : state.options.length > 0 ? (
    <div className="grid grid-cols-1 gap-1.5 mt-3">
      {state.options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => handlePick(opt)}
          disabled={state.loading}
          className="text-left text-xs px-3 py-2 rounded-lg bg-nxt-panel/80 hover:bg-nxt-panel text-nxt-text border border-nxt-border transition disabled:opacity-50"
        >
          {opt}
        </button>
      ))}
    </div>
  ) : null;

  // ---- bgUrl variant ----
  if (bgUrl) {
    return (
      <div className="relative h-full w-full overflow-hidden rounded-2xl border border-nxt-border shadow-panel">
        <img
          src={bgUrl}
          alt="Office pantry"
          className="absolute inset-0 w-full h-full object-cover"
          draggable={false}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'linear-gradient(180deg, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.75) 100%)',
          }}
        />
        <div className="absolute top-3 left-3 z-20 text-[10px] uppercase tracking-[0.18em] text-white/85">
          Pantry · Coffee break
        </div>

        {arjunPortrait && (
          <motion.img
            src={arjunPortrait}
            alt="Arjun"
            initial={{ x: 80, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 0.45, ease: 'easeOut', delay: 0.1 }}
            className="absolute"
            style={{
              bottom: '8%',
              right: '5%',
              height: '60%',
              filter: 'drop-shadow(0 10px 16px rgba(0,0,0,0.5))',
            }}
            draggable={false}
          />
        )}

        <div className="absolute top-12 left-3 right-3 bottom-3 z-10 flex flex-col">
          <div className="flex-1 min-h-0 overflow-y-auto pr-1">{transcript}</div>
          <div className="shrink-0">{controls}</div>
        </div>
      </div>
    );
  }

  // ---- CSS fallback ----
  return (
    <div
      className="relative h-full w-full overflow-hidden rounded-2xl border border-nxt-border shadow-panel"
      style={{
        background:
          'radial-gradient(ellipse at 30% 45%, #2b1d12 0%, #1a1310 60%, #110d0a 100%)',
      }}
    >
      <div className="absolute top-3 left-3 text-[10px] uppercase tracking-wider text-nxt-muted">
        Pantry · Coffee break
      </div>

      {/* Coffee machine */}
      <div className="absolute top-12 left-4 w-20 h-28 opacity-90">
        <div className="absolute inset-0 rounded-md border-2 border-nxt-wood bg-nxt-coffee/85 shadow-panel">
          <div className="absolute top-2 left-2 right-2 h-1.5 rounded bg-nxt-wood" />
          <div className="absolute top-5 left-2 right-2 h-8 rounded bg-nxt-bg/80 border border-nxt-wood" />
          <div className="absolute bottom-2 left-2 right-2 h-1 bg-nxt-wood rounded" />
        </div>
        {!reduce && (
          <div className="absolute -top-3 left-6 w-1.5 h-1.5 rounded-full bg-nxt-text/40 animate-steam" />
        )}
      </div>

      {/* Arjun avatar in corner */}
      <motion.div
        initial={{ x: 60, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="absolute bottom-4 right-4"
      >
        <CharacterAvatar character="arjun" expression="happy" size={56} />
      </motion.div>

      <div className="absolute top-12 left-4 right-4 bottom-4 z-10 flex flex-col pl-24">
        <div className="flex-1 min-h-0 overflow-y-auto pr-1">{transcript}</div>
        <div className="shrink-0">{controls}</div>
      </div>
    </div>
  );
}
