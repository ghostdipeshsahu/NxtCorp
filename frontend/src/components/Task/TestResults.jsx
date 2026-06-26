import { motion, useReducedMotion } from 'framer-motion';
import CountUp from '../UI/CountUp.jsx';

function fmt(v) {
  return JSON.stringify(v);
}

function PassMark() {
  return (
    <motion.span
      initial={{ scale: 0 }}
      animate={{ scale: [0, 1.25, 1] }}
      transition={{ duration: 0.35, times: [0, 0.6, 1] }}
      className="inline-block text-nxt-green font-medium"
    >
      ✔ PASS
    </motion.span>
  );
}

function FailMark() {
  const reduce = useReducedMotion();
  const anim = reduce
    ? { opacity: 1 }
    : { x: [0, -4, 4, -3, 3, 0], opacity: 1 };
  return (
    <motion.span
      initial={{ opacity: 0 }}
      animate={anim}
      transition={{ duration: 0.45 }}
      className="inline-block text-nxt-red font-medium"
    >
      ✕ FAIL
    </motion.span>
  );
}

export default function TestResults({ lastRun, sampleTests }) {
  if (!lastRun) {
    if (!sampleTests || sampleTests.length === 0) return null;
    return (
      <div className="mt-3 rounded-xl border border-nxt-border bg-nxt-panel/50 p-3">
        <div className="text-xs uppercase tracking-wider text-nxt-muted mb-2">
          Sample tests (shown — hidden tests run on submit)
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-nxt-muted">
              <th className="text-left font-medium py-1">Input</th>
              <th className="text-left font-medium py-1">Expected</th>
              <th className="text-left font-medium py-1">Note</th>
            </tr>
          </thead>
          <tbody>
            {sampleTests.map((t, i) => (
              <tr key={i} className="border-t border-nxt-border">
                <td className="py-1 font-mono text-nxt-text">{fmt(t.input)}</td>
                <td className="py-1 font-mono text-nxt-text">{fmt(t.expected)}</td>
                <td className="py-1 text-nxt-muted">{t.description || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const allPassed = lastRun.all_passed;
  const samplePct = lastRun.sample_total
    ? Math.round((lastRun.sample_passed / lastRun.sample_total) * 100)
    : 0;
  const hiddenPct = lastRun.hidden_total
    ? Math.round((lastRun.hidden_passed / lastRun.hidden_total) * 100)
    : 0;
  const totalPct = lastRun.sample_total + lastRun.hidden_total
    ? Math.round(
        ((lastRun.sample_passed + lastRun.hidden_passed) /
          (lastRun.sample_total + lastRun.hidden_total)) *
          100,
      )
    : 0;

  return (
    <div className="mt-3 space-y-3">
      <motion.div
        key={lastRun.attempt_id /* re-mount on new attempt */}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className={
          'rounded-xl border p-3 ' +
          (allPassed
            ? 'border-nxt-green/40 bg-nxt-green/10'
            : 'border-amber-400/40 bg-amber-400/10')
        }
      >
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-nxt-text">
            {allPassed ? '✔ All tests passed' : '⚠ Some tests failed'}
            <span className="ml-2 text-xs text-nxt-muted">
              <CountUp value={totalPct} />% overall
            </span>
          </div>
          <div className="text-xs text-nxt-muted">
            Sample {lastRun.sample_passed}/{lastRun.sample_total} ({samplePct}%) · Hidden{' '}
            {lastRun.hidden_passed}/{lastRun.hidden_total} ({hiddenPct}%)
          </div>
        </div>
        {lastRun.xp_earned > 0 && (
          <div className="text-xs text-nxt-gold mt-1">
            +{lastRun.xp_earned} XP
            {lastRun.arjun_triggered && allPassed && (
              <span className="text-nxt-muted"> — Arjun helped out on this one</span>
            )}
            {lastRun.badges_earned?.length
              ? ` · badges: ${lastRun.badges_earned.join(', ')}`
              : ''}
          </div>
        )}
      </motion.div>

      <div className="rounded-xl border border-nxt-border bg-nxt-panel/50 p-3">
        <div className="text-xs uppercase tracking-wider text-nxt-muted mb-2">
          Sample test results
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-nxt-muted">
              <th className="text-left font-medium py-1">Input</th>
              <th className="text-left font-medium py-1">Expected</th>
              <th className="text-left font-medium py-1">Actual</th>
              <th className="text-left font-medium py-1">Status</th>
            </tr>
          </thead>
          <tbody>
            {lastRun.test_results.map((r, i) => (
              <motion.tr
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: i * 0.15 }}
                className="border-t border-nxt-border"
              >
                <td className="py-1 font-mono text-nxt-text">{fmt(r.input)}</td>
                <td className="py-1 font-mono text-nxt-text">{fmt(r.expected)}</td>
                <td className="py-1 font-mono">
                  {r.error ? (
                    <span className="text-nxt-red">{r.error}</span>
                  ) : (
                    <span className="text-nxt-text">{fmt(r.actual)}</span>
                  )}
                </td>
                <td className="py-1">{r.passed ? <PassMark /> : <FailMark />}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
        <div className="text-[10px] text-nxt-muted mt-2">
          Hidden tests are run but never shown.
        </div>
      </div>
    </div>
  );
}
