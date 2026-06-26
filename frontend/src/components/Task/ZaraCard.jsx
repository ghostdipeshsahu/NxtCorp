import { motion } from 'framer-motion';
import CharacterAvatar from '../Chat/CharacterAvatar.jsx';

// v5 — Zara QA assessment card. Renders below the test results in the
// center panel after every submit. Receives the PUBLIC-SAFE payload built
// by backend/services/run_pipeline._build_public_zara_payload — no
// primary_gap, no zara_note, no gaps. Scores + flags + status_message only.
//
// Per-type score bars:
//   type_1 / type_5 → Requirement Quality + Output Quality
//   type_2          → Coverage Score + Specificity Score
//   type_3          → Identification Score + Precision Score
//   type_4          → Bug Coverage + Test Quality (+ accidentally_passing badge)
// All types also show Overall Score.
//
// Bar colors:
//   0–4   red
//   5–6   amber
//   7–8   green
//   9–10  bright green

function scoreColor(score) {
  if (score >= 9) return '#10b981'; // bright green
  if (score >= 7) return '#22c55e'; // green
  if (score >= 5) return '#f59e0b'; // amber
  return '#ef4444';                 // red
}


function ScoreBar({ label, value, delay = 0 }) {
  const v = Math.max(0, Math.min(10, Number(value) || 0));
  const pct = (v / 10) * 100;
  const color = scoreColor(v);
  return (
    <div className="mb-2">
      <div className="flex items-baseline justify-between mb-0.5">
        <div className="text-xs text-nxt-text">{label}</div>
        <div className="text-xs font-mono text-nxt-text">{v.toFixed(1)} / 10</div>
      </div>
      <div className="w-full h-2 rounded-full bg-nxt-panel overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, delay, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}


function statusIcon(kind, accidentally) {
  if (accidentally) return '⚠️';
  if (kind === 'pass') return '✅';
  if (kind === 'warning') return '⚠️';
  return '🔍';
}


function expressionFor(kind, accidentally) {
  if (accidentally) return 'concerned';
  if (kind === 'pass') return 'happy';
  if (kind === 'warning') return 'thinking';
  return 'concerned';
}


function PerTypeBars({ exerciseType, typeSpecific }) {
  const ts = typeSpecific || {};
  if (exerciseType === 'type_2') {
    return (
      <>
        <ScoreBar label="Coverage Score"    value={ts.coverage_score ?? 0}    delay={0} />
        <ScoreBar label="Specificity Score" value={ts.specificity_score ?? 0} delay={0.5} />
      </>
    );
  }
  if (exerciseType === 'type_3') {
    return (
      <>
        <ScoreBar label="Identification Score" value={ts.identification_score ?? 0} delay={0} />
        <ScoreBar label="Precision Score"      value={ts.precision_score ?? 0}      delay={0.5} />
      </>
    );
  }
  if (exerciseType === 'type_4') {
    return (
      <>
        <ScoreBar label="Bug Coverage" value={ts.bug_coverage_score ?? 0} delay={0} />
        <ScoreBar label="Test Quality" value={ts.test_quality_score ?? 0} delay={0.5} />
      </>
    );
  }
  // type_1 + type_5: requirement / output
  return null;
}


export default function ZaraCard({ assessment }) {
  if (!assessment) return null;
  const scores = assessment.scores || {};
  const ts = scores.type_specific || {};
  const et = assessment.exercise_type || 'type_1';
  const accidentally = !!assessment.accidentally_passing_flag;
  const evalWarning = !!assessment.eval_warning;

  // Sequential delays for the bar animations (0.5 s each).
  const reqQ = scores.requirement_quality ?? 0;
  const outQ = scores.output_quality ?? 0;
  const overall = scores.overall_score ?? 0;

  // For type_1 / type_5 we show requirement_quality + output_quality.
  // For others we show the per-type pair only; top-level scores stay in the
  // backend mirrors but the named bars are the per-type ones.
  const showStandardPair = et === 'type_1' || et === 'type_5';

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mt-3 rounded-xl border border-nxt-border bg-nxt-surface/85 backdrop-blur p-3 shadow-panel"
    >
      <div className="flex items-center gap-2 mb-3">
        <CharacterAvatar
          character="zara"
          expression={expressionFor(assessment.status_kind, accidentally)}
          size={32}
        />
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-wider text-nxt-muted">
            {statusIcon(assessment.status_kind, accidentally)} ZARA KHAN — QA ENGINEER
          </div>
        </div>
      </div>

      {showStandardPair ? (
        <>
          <ScoreBar label="Requirement Quality" value={reqQ} delay={0} />
          <ScoreBar label="Output Quality"      value={outQ} delay={0.5} />
        </>
      ) : (
        <PerTypeBars exerciseType={et} typeSpecific={ts} />
      )}
      <ScoreBar label="Overall Score" value={overall} delay={1.0} />

      {/* Type 1/5 pass-rate stat — surfaces the deterministic axis */}
      {(et === 'type_1' || et === 'type_5') && ts.tests_total ? (
        <div className="text-[10px] text-nxt-muted mt-1">
          {ts.tests_passed}/{ts.tests_total} tests passed ({ts.test_pass_rate}%)
          {et === 'type_5' && ts.original_pass_rate !== undefined && (
            <> · before fix {ts.original_pass_rate}% → after {ts.new_pass_rate}%</>
          )}
        </div>
      ) : null}

      {/* Public status message — never leaks primary_gap or zara_note */}
      <div
        className={
          'mt-3 px-3 py-2 rounded-md text-xs italic ' +
          (accidentally || evalWarning
            ? 'bg-amber-500/15 border border-amber-500/40 text-amber-100'
            : assessment.status_kind === 'pass'
              ? 'bg-emerald-500/15 border border-emerald-500/40 text-emerald-100'
              : 'bg-nxt-panel/60 border border-nxt-border text-nxt-text/85')
        }
      >
        {accidentally && <span className="not-italic mr-1">⚠️</span>}
        "{assessment.status_message}"
      </div>
    </motion.div>
  );
}
