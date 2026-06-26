import { useCallback, useEffect, useRef, useState } from 'react';

// Tiny Web Audio sound system. All sounds generated programmatically — no
// audio files. Off by default per spec §5. Toggle via TopBar.
//
// Sound names supported: 'submit' | 'pass' | 'fail' | 'xp' | 'promotion' |
// 'badge' | 'message' | 'type'.

const STORAGE_KEY = 'nxtcorp.sound';

function readPref() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function writePref(on) {
  try {
    localStorage.setItem(STORAGE_KEY, on ? '1' : '0');
  } catch {
    /* ignore */
  }
}

function envelope(ctx, gain, t0, attack, hold, release, peak = 0.2) {
  gain.gain.setValueAtTime(0, t0);
  gain.gain.linearRampToValueAtTime(peak, t0 + attack);
  gain.gain.linearRampToValueAtTime(peak * 0.9, t0 + attack + hold);
  gain.gain.linearRampToValueAtTime(0, t0 + attack + hold + release);
}

function tone(ctx, { freq, type = 'sine', dur = 0.18, peak = 0.18 }) {
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.value = freq;
  o.connect(g).connect(ctx.destination);
  const now = ctx.currentTime;
  envelope(ctx, g, now, 0.005, dur * 0.4, dur * 0.55, peak);
  o.start(now);
  o.stop(now + dur + 0.05);
}

function sweep(ctx, { from, to, type = 'sine', dur = 0.3, peak = 0.18 }) {
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.connect(g).connect(ctx.destination);
  const now = ctx.currentTime;
  o.frequency.setValueAtTime(from, now);
  o.frequency.exponentialRampToValueAtTime(Math.max(1, to), now + dur);
  envelope(ctx, g, now, 0.005, dur * 0.5, dur * 0.45, peak);
  o.start(now);
  o.stop(now + dur + 0.05);
}

function chord(ctx, freqs, dur = 0.35, type = 'triangle', peak = 0.12) {
  freqs.forEach((f, i) => {
    setTimeout(() => tone(ctx, { freq: f, type, dur, peak }), i * 50);
  });
}

const PLAYERS = {
  submit:    (ctx) => sweep(ctx, { from: 220, to: 660, type: 'triangle', dur: 0.22, peak: 0.15 }),
  pass:      (ctx) => chord(ctx, [523.25, 659.25, 783.99], 0.35, 'sine', 0.16),
  fail:      (ctx) => tone(ctx,  { freq: 140, type: 'sawtooth', dur: 0.28, peak: 0.16 }),
  xp:        (ctx) => sweep(ctx, { from: 440, to: 880, type: 'sine', dur: 0.32, peak: 0.14 }),
  promotion: (ctx) => chord(ctx, [392, 523.25, 659.25, 783.99], 0.55, 'triangle', 0.18),
  badge:     (ctx) => chord(ctx, [1046.5, 1318.5, 1567.98], 0.28, 'sine', 0.14),
  message:   (ctx) => tone(ctx,  { freq: 660, type: 'sine', dur: 0.12, peak: 0.12 }),
  type:      (ctx) => tone(ctx,  { freq: 1200, type: 'square', dur: 0.02, peak: 0.05 }),
};

export function useSound() {
  const [soundOn, setSoundOn] = useState(readPref);
  const ctxRef = useRef(null);

  useEffect(() => {
    if (!soundOn) return;
    // Lazily create the AudioContext on the first call after enabling.
    try {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      if (!ctxRef.current && Ctor) ctxRef.current = new Ctor();
    } catch {
      /* ignore */
    }
  }, [soundOn]);

  const play = useCallback(
    (name) => {
      if (!soundOn) return;
      const ctx = ctxRef.current;
      if (!ctx) return;
      // Some browsers suspend the context until user gesture.
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      const fn = PLAYERS[name];
      if (fn) {
        try {
          fn(ctx);
        } catch {
          /* swallow audio errors */
        }
      }
    },
    [soundOn],
  );

  const toggleSound = useCallback(() => {
    setSoundOn((on) => {
      const next = !on;
      writePref(next);
      return next;
    });
  }, []);

  return { play, soundOn, toggleSound };
}
