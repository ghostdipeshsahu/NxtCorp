import { useEffect, useRef, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import Message from './Message.jsx';

export default function ChatPanel({ messages, playerName, avatarId, onRespond, respondBusy }) {
  const [text, setText] = useState('');
  const scrollerRef = useRef(null);

  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  function submit(e) {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    onRespond(t);
    setText('');
  }

  return (
    <div className="h-full rounded-2xl bg-nxt-surface/80 backdrop-blur border border-nxt-border shadow-panel flex flex-col overflow-hidden">
      <div className="px-3 py-2 border-b border-nxt-border flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-nxt-green animate-pulse" />
        <div className="text-sm font-medium text-nxt-text">#team-chat</div>
        <div className="ml-auto text-[10px] text-nxt-muted uppercase tracking-wider">
          Slack-style
        </div>
      </div>

      <div ref={scrollerRef} className="flex-1 min-h-0 overflow-y-auto px-3 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-sm text-nxt-muted text-center py-8">No messages yet.</div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <Message
              key={m.id}
              message={m}
              playerName={playerName}
              playerAvatarId={avatarId}
            />
          ))}
        </AnimatePresence>
      </div>

      <form onSubmit={submit} className="border-t border-nxt-border p-2 flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Reply to Priya…"
          disabled={respondBusy}
          className="flex-1 rounded-lg bg-nxt-panel border border-nxt-border text-nxt-text placeholder-nxt-muted px-3 py-2 text-sm focus:outline-none focus:border-nxt-accent disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={respondBusy || !text.trim()}
          className="rounded-lg bg-nxt-accent hover:brightness-110 disabled:opacity-40 text-white text-sm font-medium px-3 transition"
        >
          {respondBusy ? '…' : 'Send'}
        </button>
      </form>
    </div>
  );
}
