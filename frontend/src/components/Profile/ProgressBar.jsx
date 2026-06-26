// Thin reusable progress bar. `value` and `max` are numbers; pct clamps to [0, 100].
export default function ProgressBar({ value = 0, max = 1, color = 'bg-nxt-500', height = 'h-2' }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className={`w-full ${height} rounded-full bg-ink-100 overflow-hidden`}>
      <div
        className={`h-full ${color} rounded-full transition-all`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
