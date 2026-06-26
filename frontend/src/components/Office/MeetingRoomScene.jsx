import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';

// v4 — Meeting Room scene.
//
// Plays out `meeting_script` (list of {character, name, role, message}) one
// message at a time with a 1.5 s gap. Student takes free-text notes on the
// right; notes auto-save up to the App via `onNotesChange`. When playback
// finishes the student clicks "Go to my desk →" which fires `onDone(notes)`.
//
// Copy protection (transcript only): no text-selection, no copy/contextmenu,
// blur overlay on document.hidden.

const MESSAGE_DELAY_MS = 4500;


function MeetingMessage({ entry, isLatest }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 1.2, ease: 'easeInOut' }}
      className="flex gap-3 items-start"
      style={{ userSelect: 'none', WebkitUserSelect: 'none', MozUserSelect: 'none' }}
    >
      <div className="shrink-0 flex flex-col items-center">
        <CharacterAvatar character={entry.character} expression="happy" size={44} />
        <div className="text-[9px] text-nxt-text mt-1 font-medium leading-tight text-center">
          {entry.name}
        </div>
        <div className="text-[8px] text-nxt-muted leading-tight text-center">
          {entry.role}
        </div>
      </div>
      <div
        className={
          'flex-1 px-3 py-2 rounded-xl rounded-tl-sm bg-nxt-panel/85 border border-nxt-border text-sm text-nxt-text whitespace-pre-wrap leading-snug shadow-panel ' +
          (isLatest ? 'ring-1 ring-nxt-lamp/40' : '')
        }
      >
        {entry.message}
      </div>
    </motion.div>
  );
}


function ConferenceTable() {
  // Static SVG conference room — table + chairs + NxtCorp wall logo.
  // Pure decoration behind the playback panel.
  return (
    <svg viewBox="0 0 320 220" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
      <defs>
        <radialGradient id="mr_light" cx="50%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#3a2a1c" />
          <stop offset="100%" stopColor="#1a120b" />
        </radialGradient>
        <linearGradient id="mr_table" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#4a3528" />
          <stop offset="100%" stopColor="#2c1d14" />
        </linearGradient>
      </defs>
      {/* Back wall */}
      <rect x="0" y="0" width="320" height="220" fill="url(#mr_light)" />
      {/* NxtCorp logo */}
      <text x="160" y="34" textAnchor="middle" fontFamily="Fraunces, Georgia, serif"
            fontSize="16" fill="#f5c842" opacity="0.85" letterSpacing="3">
        NxtCorp
      </text>
      <text x="160" y="48" textAnchor="middle" fontFamily="sans-serif"
            fontSize="6" fill="#8a7a6a" letterSpacing="3">
        HYDERABAD OFFICE
      </text>
      {/* Hanging pendant light */}
      <line x1="160" y1="0" x2="160" y2="62" stroke="#3d2918" strokeWidth="1" />
      <ellipse cx="160" cy="68" rx="20" ry="6" fill="#3d2918" stroke="#1a1108" strokeWidth="1.5" />
      <ellipse cx="160" cy="72" rx="34" ry="14" fill="rgba(245,166,35,0.18)" />
      {/* Conference table */}
      <polygon points="60,150 260,150 280,180 40,180" fill="url(#mr_table)" stroke="#1a1108" strokeWidth="1.5" />
      <polygon points="60,150 260,150 256,154 64,154" fill="rgba(245,166,35,0.25)" />
      {/* Chairs around the table */}
      {[60, 110, 160, 210, 260].map((cx, i) => (
        <g key={i}>
          {/* chair back */}
          <rect x={cx - 12} y={120} width="24" height="22" rx="3" fill="#1a1108" />
          <rect x={cx - 10} y={123} width="20" height="16" rx="2" fill="#3d2918" opacity="0.7" />
        </g>
      ))}
      {/* Floor shadow */}
      <ellipse cx="160" cy="185" rx="160" ry="14" fill="rgba(0,0,0,0.5)" />
      {/* Vignette */}
      <rect x="0" y="0" width="320" height="220" fill="url(#mr_vignette)" />
      <radialGradient id="mr_vignette" cx="50%" cy="50%" r="70%">
        <stop offset="60%" stopColor="rgba(0,0,0,0)" />
        <stop offset="100%" stopColor="rgba(0,0,0,0.5)" />
      </radialGradient>
    </svg>
  );
}


export default function MeetingRoomScene({
  script = [],
  initialNotes = '',
  onDone,
  onNotesChange,
}) {
  const reduce = useReducedMotion();
  const safeScript = useMemo(
    () => (Array.isArray(script) ? script.filter((e) => e && e.message) : []),
    [script],
  );
  const totalMessages = safeScript.length;

  const [visibleCount, setVisibleCount] = useState(totalMessages === 0 ? 0 : 1);
  const [notes, setNotes] = useState(initialNotes);
  const [paused, setPaused] = useState(false);
  const timeoutRef = useRef(null);

  // Bubble up notes to the parent as the student types.
  useEffect(() => {
    onNotesChange?.(notes);
  }, [notes, onNotesChange]);

  // Drive the 1.5 s playback timer. Pauses while the document is hidden.
  useEffect(() => {
    if (paused) return undefined;
    if (visibleCount === 0) return undefined;
    if (visibleCount >= totalMessages) return undefined;
    timeoutRef.current = setTimeout(() => {
      setVisibleCount((n) => Math.min(n + 1, totalMessages));
    }, MESSAGE_DELAY_MS);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [visibleCount, totalMessages, paused]);

  // Focus / visibility protection — pause when student tabs away. Resume
  // from the same message index when they come back (no auto-replay).
  useEffect(() => {
    function onVisChange() {
      setPaused(document.hidden);
    }
    document.addEventListener('visibilitychange', onVisChange);
    return () => document.removeEventListener('visibilitychange', onVisChange);
  }, []);

  function handleReplay() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisibleCount(totalMessages === 0 ? 0 : 1);
  }

  const transcriptDone = totalMessages === 0 || visibleCount >= totalMessages;

  // Block copy / context menu inside the transcript panel.
  const protect = {
    onCopy: (e) => e.preventDefault(),
    onCut: (e) => e.preventDefault(),
    onContextMenu: (e) => e.preventDefault(),
    style: { userSelect: 'none', WebkitUserSelect: 'none', MozUserSelect: 'none' },
  };

  const visibleEntries = safeScript.slice(0, visibleCount);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-2xl border border-nxt-border shadow-panel">
      {/* Background — conference room */}
      <div className="absolute inset-0">
        <ConferenceTable />
      </div>
      <div className="absolute inset-0 pointer-events-none"
           style={{
             background:
               'linear-gradient(180deg, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0.1) 30%, rgba(0,0,0,0.1) 70%, rgba(0,0,0,0.65) 100%)',
           }}
      />
      <div className="absolute top-3 left-3 z-20 text-[10px] uppercase tracking-[0.18em] text-white/85">
        Meeting Room · Hyderabad Office
      </div>

      {/* Two-column layout: transcript (left) + notes (right) */}
      <div className="relative z-10 h-full w-full grid grid-cols-5 gap-3 p-3 pt-10 pb-3">
        {/* === Transcript === */}
        <div
          className="col-span-3 flex flex-col min-h-0 rounded-xl bg-black/55 backdrop-blur border border-nxt-border p-3"
          {...protect}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] uppercase tracking-wider text-white/70">
              Briefing transcript
            </div>
            {totalMessages > 0 && (
              <button
                type="button"
                onClick={handleReplay}
                disabled={transcriptDone === false && visibleCount === 1}
                className="text-[10px] px-2 py-1 rounded border border-nxt-border bg-nxt-panel/80 text-nxt-text hover:bg-nxt-panel transition"
              >
                ↻ Replay
              </button>
            )}
          </div>

          {totalMessages === 0 ? (
            <div className="flex-1 grid place-items-center text-center text-xs text-white/70 italic">
              Meeting script coming soon.<br />
              Head straight to your desk.
            </div>
          ) : (
            <div className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-1">
              {visibleEntries.map((entry, i) => (
                <MeetingMessage
                  key={i}
                  entry={entry}
                  isLatest={i === visibleEntries.length - 1}
                />
              ))}
            </div>
          )}

          {transcriptDone && (
            <button
              type="button"
              onClick={() => onDone?.(notes)}
              className="mt-3 w-full rounded-lg bg-nxt-accent hover:brightness-110 text-white text-sm font-medium py-2 shadow-panel"
            >
              Go to my desk →
            </button>
          )}
        </div>

        {/* === Notes panel === */}
        <div className="col-span-2 flex flex-col min-h-0 rounded-xl bg-nxt-surface/90 backdrop-blur border border-nxt-border p-3">
          <div className="text-[10px] uppercase tracking-wider text-nxt-muted mb-2">
            My Notes
          </div>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Take notes as stakeholders speak. Capture every rule, number, and condition they mention. These notes are the only thing you will have when writing your AI instructions."
            spellCheck={false}
            className="flex-1 min-h-0 w-full resize-none rounded-lg bg-nxt-panel/80 border border-nxt-border text-sm text-nxt-text p-2 font-mono leading-snug focus:outline-none focus:ring-1 focus:ring-nxt-accent"
          />
          <div className="mt-2 text-[10px] text-nxt-muted italic">
            Auto-saved. Read-only once you leave.
          </div>
        </div>
      </div>

      {/* Focus-loss overlay */}
      <AnimatePresence>
        {paused && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 z-30 grid place-items-center backdrop-blur-md bg-black/70"
          >
            <div className="text-center text-white">
              <div className="text-4xl mb-3">👀</div>
              <div className="font-display text-lg">Come back to the meeting!</div>
              <div className="text-xs text-white/70 mt-1 italic">
                Playback paused. Resumes when you return.
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
