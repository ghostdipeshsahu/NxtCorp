import { useState } from 'react';
import { motion } from 'framer-motion';
import { login, register } from '../../api.js';

export default function Login({ onAuthed }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === 'login') {
        await login({ username, password });
      } else {
        await register({
          username,
          password,
          display_name: username,
          avatar_id: 'avatar_02',
        });
      }
      onAuthed();
    } catch (err) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full grid place-items-center bg-nxt-bg p-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
        className="w-full max-w-sm rounded-2xl bg-nxt-surface border border-nxt-border shadow-panel p-8"
      >
        <div className="flex items-center gap-2 mb-6">
          <div className="w-9 h-9 rounded-lg bg-nxt-accent grid place-items-center text-white font-display font-semibold shadow-panel">
            N
          </div>
          <h1 className="font-display text-2xl text-nxt-text">NxtCorp</h1>
        </div>
        <p className="text-nxt-muted text-sm mb-6">
          {mode === 'login'
            ? 'Welcome back. Sign in to continue.'
            : 'Create your account. You’ll pick a name and avatar next.'}
        </p>

        <form onSubmit={submit} className="space-y-3">
          <input
            className="w-full rounded-lg bg-nxt-panel border border-nxt-border text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm focus:outline-none focus:border-nxt-accent"
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
            minLength={3}
          />
          <input
            className="w-full rounded-lg bg-nxt-panel border border-nxt-border text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm focus:outline-none focus:border-nxt-accent"
            type="password"
            placeholder="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
            minLength={6}
          />

          {error && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <motion.button
            type="submit"
            disabled={busy}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            className="w-full rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-50 text-white font-medium py-2 transition shadow-panel"
          >
            {busy ? '…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </motion.button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login');
            setError(null);
          }}
          className="text-xs text-nxt-muted hover:text-nxt-accent mt-4"
        >
          {mode === 'login' ? 'New here? Create an account →' : 'Have an account? Sign in →'}
        </button>
      </motion.div>
    </div>
  );
}
