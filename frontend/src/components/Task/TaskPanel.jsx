import PromptEditor from './PromptEditor.jsx';
import SubtaskEditor from './SubtaskEditor.jsx';
import GapEditor from './GapEditor.jsx';
import TestCaseEditor from './TestCaseEditor.jsx';
import DiagnoseContext from './DiagnoseContext.jsx';
import TestResults from './TestResults.jsx';
import ZaraCard from './ZaraCard.jsx';

// v3 numbering. The implementation each editor uses is unchanged; only the
// type label flips.
const TYPE_LABELS = {
  1: 'Type 1 · Prompt AI to Build',
  2: 'Type 2 · Decompose Vague Work',
  3: 'Type 3 · Predict AI Failure',
  4: 'Type 4 · Verify AI Output',
  5: 'Type 5 · Improve AI After Failure',
};

export default function TaskPanel({
  task,
  attemptNumber,
  running,
  onRun,
  lastRun,
  loading,
  inCabin = false,
  inMeeting = false,
  onStartTask,
}) {
  if (loading) {
    return (
      <div className="h-full rounded-2xl bg-nxt-surface/80 backdrop-blur border border-nxt-border shadow-panel p-6 text-nxt-muted text-sm">
        Loading your ticket…
      </div>
    );
  }
  if (!task) {
    return (
      <div className="h-full rounded-2xl bg-nxt-surface/80 backdrop-blur border border-nxt-border shadow-panel p-6 text-nxt-muted text-sm">
        No ticket assigned.
      </div>
    );
  }

  const exerciseType = Number(task.exercise_type ?? 1);
  const disabled = !!lastRun?.all_passed;

  // Choose the editor surface (v3 numbering)
  let editor;
  if (exerciseType === 1) {
    // Type 1: Prompt AI to Build — student writes a complete prompt
    editor = (
      <PromptEditor
        onRun={onRun}
        running={running}
        attemptNumber={attemptNumber}
        disabled={disabled}
      />
    );
  } else if (exerciseType === 2) {
    // Type 2: Decompose Vague Work — student lists sub-tasks
    editor = (
      <SubtaskEditor
        task={task}
        onRun={onRun}
        running={running}
        attemptNumber={attemptNumber}
        disabled={disabled}
      />
    );
  } else if (exerciseType === 3) {
    // Type 3: Predict AI Failure Cases — student lists what could break
    editor = (
      <GapEditor
        task={task}
        onRun={onRun}
        running={running}
        attemptNumber={attemptNumber}
        disabled={disabled}
      />
    );
  } else if (exerciseType === 4) {
    editor = (
      <TestCaseEditor
        task={task}
        onRun={onRun}
        running={running}
        attemptNumber={attemptNumber}
        disabled={disabled}
      />
    );
  } else if (exerciseType === 5) {
    editor = (
      <>
        <DiagnoseContext task={task} />
        <PromptEditor
          onRun={onRun}
          running={running}
          attemptNumber={attemptNumber}
          disabled={disabled}
        />
      </>
    );
  } else {
    editor = (
      <PromptEditor
        onRun={onRun}
        running={running}
        attemptNumber={attemptNumber}
        disabled={disabled}
      />
    );
  }

  return (
    <div className="h-full rounded-2xl bg-nxt-surface/80 backdrop-blur shadow-ticket border border-nxt-border overflow-hidden flex flex-col">
      {/* JIRA-like header bar */}
      <div className="px-4 py-2 border-b border-nxt-border flex items-center gap-2 bg-nxt-panel/60">
        <div className="px-2 py-0.5 rounded-md bg-nxt-accent text-white text-[10px] font-medium uppercase tracking-wider">
          {task.question_id.split('_')[0].toUpperCase()}
        </div>
        <div className="text-sm font-medium text-nxt-text">{task.title}</div>
        <div className="ml-auto text-[10px] uppercase tracking-wider text-nxt-muted">
          {TYPE_LABELS[exerciseType] || `Type ${exerciseType}`}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
        {/* v4 Change 7: task description card removed. Rules are now
            delivered through the Meeting Room briefing — the only
            artifacts the student gets at the desk are the function
            signature, the sample tests, and their own meeting notes. */}

        {task.function_signature && exerciseType !== 4 && (
          <div>
            <div className="text-xs uppercase tracking-wider text-nxt-muted mb-1">
              Function signature
            </div>
            <code className="block text-sm font-mono bg-nxt-panel border border-nxt-border text-nxt-text rounded-lg px-3 py-1.5">
              {task.function_signature}
            </code>
          </div>
        )}

        {inCabin ? (
          <div className="rounded-xl border border-nxt-accent/50 bg-nxt-accent/10 p-4 text-center">
            {task.meeting_completed ? (
              <>
                <div className="text-sm text-nxt-text mb-3">
                  Head back to your desk when you're ready to keep working on this ticket.
                </div>
                <button
                  type="button"
                  onClick={onStartTask}
                  className="rounded-lg bg-nxt-accent hover:brightness-110 text-white font-medium px-5 py-2 transition shadow-panel"
                >
                  Back to my desk →
                </button>
              </>
            ) : (
              <>
                <div className="text-sm text-nxt-text mb-3">
                  New ticket just came in. Head to the meeting room first — the stakeholders will explain what they need. Take good notes. You will need them at your desk.
                </div>
                <button
                  type="button"
                  onClick={onStartTask}
                  className="rounded-lg bg-nxt-accent hover:brightness-110 text-white font-medium px-5 py-2 transition shadow-panel"
                >
                  Join Meeting →
                </button>
              </>
            )}
          </div>
        ) : inMeeting ? (
          <div className="rounded-xl border border-nxt-border bg-nxt-panel/60 p-4 text-center text-sm text-nxt-muted">
            <div className="text-base mb-1">📋</div>
            You're in the briefing. The editor opens at your desk.
          </div>
        ) : (
          <>
            {editor}
            <TestResults lastRun={lastRun} sampleTests={task.sample_tests} />
            {lastRun?.zara_assessment && (
              <ZaraCard assessment={lastRun.zara_assessment} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
