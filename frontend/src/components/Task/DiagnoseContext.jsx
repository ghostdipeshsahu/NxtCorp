// Type 5 — Diagnose and Fix.
//
// Renders the failing prompt + the inputs that the failing prompt likely
// mis-handles, above the regular PromptEditor. The student writes a NEW
// prompt that fixes the gap. Backend pipeline is identical to Type 3 — the
// student's new prompt goes through codegen + executor + assessor.

export default function DiagnoseContext({ task }) {
  const failing = task?.failing_prompt || '';
  const hints = Array.isArray(task?.failing_inputs_hint) ? task.failing_inputs_hint : [];

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-nxt-lamp/40 bg-nxt-lamp/10 px-3 py-2 text-xs text-nxt-text/85">
        <span className="font-medium text-nxt-lamp">Type 5 · Improve AI After Failure</span>
        <div className="text-nxt-muted mt-0.5">
          This was built using AI and QA rejected it. Look at what failed and
          why — then fix the instructions precisely. Use your notes from the
          meeting to identify what the original prompt missed. Don't rewrite
          everything — add only what is missing.
        </div>
      </div>

      <div className="rounded-xl border border-nxt-red/40 bg-nxt-red/10 p-3">
        <div className="text-[10px] uppercase tracking-wider text-nxt-red mb-1">
          ⚠ Failing prompt (yesterday's attempt — QA rejected it)
        </div>
        <div className="text-sm text-nxt-text/95 whitespace-pre-wrap leading-relaxed">
          {failing || '(no failing_prompt available)'}
        </div>
      </div>

      {hints.length > 0 && (
        <div className="text-xs text-nxt-muted">
          QA reported these inputs broke it:&nbsp;
          {hints.map((h, i) => (
            <span key={i} className="inline-block mx-1 px-1.5 py-0.5 rounded bg-nxt-panel border border-nxt-border font-mono text-nxt-text">
              {JSON.stringify(h)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
