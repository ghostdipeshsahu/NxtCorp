import { useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';
import { getSceneBackground } from '../../assets/index.js';

function initialsOf(name = '') {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0 || !parts[0]) return '??';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}


// Collapsed-by-default sticky-note panel pinned to the bottom-left of the
// desk scene. Shows the student's Meeting Room notes in read-only mode —
// no edits allowed at the desk. v4.
function NotesPanel({ notes }) {
  const [open, setOpen] = useState(false);
  if (!notes || !notes.trim()) return null;
  return (
    <div className="absolute bottom-3 left-3 z-20 max-w-[55%]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-nxt-panel/95 border border-nxt-border text-[10px] uppercase tracking-wider text-nxt-text hover:brightness-110 shadow-panel backdrop-blur"
      >
        📝 Meeting Notes (read only)
        <span className="text-nxt-muted">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div
          className="mt-1 max-h-48 overflow-y-auto rounded-md bg-amber-100/95 text-stone-800 text-xs leading-snug px-3 py-2 shadow-panel border border-amber-300/70 whitespace-pre-wrap font-mono"
          style={{ width: 'min(420px, 90vw)' }}
        >
          {notes}
        </div>
      )}
    </div>
  );
}


export default function DeskScene({ profile, task, meetingNotes = '' }) {
  // v3: voluntary hint button removed. Arjun is now auto-triggered after
  // the 3rd failed attempt and surfaced via a toast notification; the
  // desk no longer offers a manual coffee-machine fallback.
  const reduce = useReducedMotion();
  const bgUrl = getSceneBackground('desk');

  // Monitor content tracks the CURRENT task only. Never carry code from a
  // previous task — at Attempt #1 the monitor is empty except for the task
  // id line + a blinking cursor (the student hasn't written anything yet).
  const taskTag = task?.question_id
    ? task.question_id.split('_')[0].toUpperCase()
    : '—';
  const taskTitle = task?.title || '';
  const taskSig = task?.function_signature || '';

  if (bgUrl) {
    return (
      <div className="relative h-full w-full overflow-hidden rounded-2xl border border-nxt-border shadow-panel">
        <img
          src={bgUrl}
          alt="Your desk"
          className="absolute inset-0 w-full h-full object-cover"
          draggable={false}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'linear-gradient(180deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.7) 100%)',
          }}
        />
        <div className="absolute top-3 left-3 z-20 text-[10px] uppercase tracking-[0.18em] text-white/85">
          Your Desk · Hyderabad Office
        </div>
        {/* Nameplate */}
        <div
          className="absolute"
          style={{
            bottom: '10%',
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '3px 10px',
            background: 'rgba(20,15,10,0.85)',
            border: '1px solid #5a3f2e',
            borderRadius: '3px',
            color: '#f0e6d3',
            fontSize: '11px',
            letterSpacing: '0.08em',
            fontFamily: 'Fraunces, Georgia, serif',
            boxShadow: '0 4px 6px rgba(0,0,0,0.5)',
          }}
        >
          {initialsOf(profile?.display_name || 'You')} · {profile?.display_name || 'Junior dev'}
        </div>
        <NotesPanel notes={meetingNotes} />
      </div>
    );
  }

  return (
    <div
      className="relative h-full w-full overflow-hidden rounded-2xl border border-nxt-border shadow-panel"
      style={{
        background:
          'radial-gradient(ellipse at 40% 35%, #221a12 0%, #14110d 60%, #0e0c09 100%)',
      }}
    >
      {/* Small back-wall window */}
      <div className="absolute top-4 right-5 w-24 h-14 rounded border-2 border-nxt-wood overflow-hidden"
           style={{ background: 'linear-gradient(180deg, #0c0c1d 0%, #1a1024 100%)' }}>
        <div className="absolute inset-0 grid grid-cols-2"><div className="border-r border-nxt-wood/60" /></div>
      </div>

      {/* Top-left floor tag */}
      <div className="absolute top-3 left-3 text-[10px] uppercase tracking-wider text-nxt-muted">
        Your Desk · Hyderabad Office
      </div>

      {/* Monitor */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 w-56 h-32">
        {/* monitor body */}
        <div className="absolute inset-0 rounded-md bg-nxt-bg border-2 border-nxt-wood shadow-panel">
          <div className="absolute inset-1 rounded-sm overflow-hidden"
               style={{ background: 'linear-gradient(180deg, #0c1218 0%, #0a161c 100%)' }}>
            {/* Monitor content — keyed on the current task so it resets
                cleanly whenever the student moves to a new ticket. Shows
                an empty-editor state: task tag + signature stub + cursor.
                Never carries code from the previous task. */}
            <div
              key={task?.question_id || 'empty'}
              className="p-2 font-mono text-[7px] leading-tight text-nxt-green/85"
            >
              <div className="text-nxt-muted/60">$ ticket {taskTag}</div>
              {taskTitle && (
                <div className="text-nxt-muted/60 truncate"># {taskTitle}</div>
              )}
              {taskSig ? (
                <div className="text-nxt-blue truncate">{taskSig}</div>
              ) : (
                <div className="text-nxt-muted/60">(awaiting ticket)</div>
              )}
              <div>{'    '}</div>
              <div className="text-nxt-lamp animate-flicker">_</div>
            </div>
          </div>
        </div>
        {/* monitor stand */}
        <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 w-8 h-5 bg-nxt-wood" />
        <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 w-20 h-2 rounded bg-nxt-wood" />
      </div>

      {/* Desk surface */}
      <div className="absolute bottom-0 left-0 right-0 h-32"
           style={{ background: 'linear-gradient(180deg, #4a3528 0%, #3d2b1f 60%, #2c1d14 100%)' }}>
        <div className="absolute top-0 left-0 right-0 h-px bg-nxt-lamp/40" />
      </div>

      {/* Desk lamp glow */}
      <div className="absolute bottom-16 left-6 w-32 h-32 rounded-full pointer-events-none animate-flicker"
           style={{ background: 'radial-gradient(circle, rgba(245,166,35,0.3) 0%, rgba(245,166,35,0) 70%)' }} />
      {/* Lamp itself */}
      <div className="absolute bottom-20 left-10 flex flex-col items-center">
        <div className="w-2.5 h-2.5 rounded-full bg-nxt-lamp animate-flicker shadow-lamp" />
        <div className="w-0.5 h-10 bg-nxt-wood -mt-1" />
        <div className="w-5 h-2 rounded-b-full bg-nxt-wood -mt-0.5" />
      </div>

      {/* Coffee mug */}
      <div className="absolute bottom-12 right-12 flex items-end gap-0.5">
        <div className="w-7 h-8 rounded-b-md bg-nxt-coffee border border-nxt-wood relative">
          <div className="absolute top-1 left-1 right-1 h-1.5 rounded-full bg-nxt-coffee" />
          {/* steam */}
          {!reduce && (
            <>
              <div className="absolute -top-3 left-1 w-1 h-1 rounded-full bg-nxt-text/40 animate-steam" />
              <div className="absolute -top-3 left-3 w-1 h-1 rounded-full bg-nxt-text/40 animate-steam" style={{ animationDelay: '0.7s' }} />
            </>
          )}
        </div>
        <div className="w-2 h-4 border border-nxt-coffee rounded-full mb-1" />
      </div>

      {/* Nameplate with initials */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded bg-nxt-wood text-nxt-text text-xs font-display tracking-wide border border-nxt-woodlight">
        {initialsOf(profile?.display_name || 'You')}
      </div>

      {/* Player avatar peeking at the desk (small) */}
      <div className="absolute bottom-12 left-20 opacity-95">
        <CharacterAvatar
          character="player"
          avatarId={profile?.avatar_id || 'avatar_02'}
          expression="thinking"
          size={56}
        />
      </div>
      <NotesPanel notes={meetingNotes} />
    </div>
  );
}
