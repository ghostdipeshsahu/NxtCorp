"""
Assessor Agent (step 4).

Scores a student attempt on three axes:

- requirement_score (0-10, LLM-judged): how complete and precise is the
  student's prompt vs. what the spec actually requires? Picks up omissions
  ("forgot the all-lowercase case") and commissions ("invented a rule the
  spec didn't mention").
- output_score (0-10, deterministic): 10 * (passed / total) across all tests
  the executor ran.
- overall_score (0-10): weighted combination, requirement-heavier because
  passing tests by accident on a vague prompt is not real understanding.

It also identifies the SINGLE primary gap from the question's gap taxonomy
that best explains the failing tests. This key is what the Coach Agent uses
to pick the right Socratic question. If everything passed, `primary_gap`
is None.

Outputs go to the Coach Agent — never directly to the student (spec §8).
The student NEVER sees: reference prompt, reference code, gap keys, or the
raw Assessor reasoning. They see only what Coach decides to surface.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.core.code_executor import ExecutionResult
from backend.core.llm import chat as llm_chat, extract_json


# Weight: requirement quality matters more than test pass rate. A vague
# prompt that accidentally passes most tests is not a sign of real
# understanding — we want to reward precise thinking, not lucky outputs.
REQUIREMENT_WEIGHT = 0.6
OUTPUT_WEIGHT = 0.4


SYSTEM_PROMPT = """You are Zara Khan, QA Engineer at NxtCorp Hyderabad.

You are sharp, precise, and detail-obsessed. You speak only to Priya — never to the student directly.

You receive:
- student_attempt: what the student submitted (prompt, decomposition, predictions, test cases, or fix)
- generated_code: the code AI produced from the student's attempt (Type 1 and 5 only)
- meeting_script: exactly what was said in the meeting
- exercise_type: which type this is

Your job:

Step 1 — Understand the meeting:
Read the meeting script carefully. Extract every rule, value, constraint, and condition that was stated. Note what was NOT stated — genuine gaps that business people forgot.

Step 2 — Read the generated code:
For Type 1 and 5: read the code directly. Reason about what it does and doesn't do. Do not run tests — reason about the code.

Step 3 — Compare:
What did the meeting say? What did the student's attempt specify? What did the generated code implement? Where do these diverge?

Step 4 — Find genuine edge cases:
Think about what real-world inputs could cause this code to give wrong results. Only include edge cases that:
- Are realistic — they actually happen
- The student could have anticipated from the meeting
- The student did not specify

Do NOT include:
- Impossible scenarios (zero salary, negative years)
- Edge cases that are too obscure
- Edge cases the meeting had no hint of

Step 5 — Score (two axes only):
coverage_score (0-10): What FRACTION of the rules / constraints / conditions
  from the meeting did the student's attempt actually address? Walk every
  rule in the meeting; score by how many were covered.
specificity_score (0-10): For the parts the student DID address, how
  PRECISELY were they stated? Vague hand-waves score low; exact values,
  named conditions, and explicit return shapes score high.

DO NOT emit `overall_score`. The backend computes it from your two scores.
DO NOT emit `requirement_quality` or `output_quality`. Those are legacy
field names — use `coverage_score` and `specificity_score` only.

Step 6 — Write zara_note:
Tell Priya exactly:
- What the student got right
- What specific gap was missed
- Which character mentioned it in the meeting (if relevant)
- Why this matters — what will go wrong if not fixed
- Do NOT state the fix or correct value

Output format (JSON only — start with `{` end with `}`, no markdown):

{
  "gaps_covered": ["<short phrase>", ...],
  "gaps_missing": ["<short phrase>", ...],
  "primary_gap": "<short phrase>",
  "genuine_edge_cases": ["<short phrase>", ...],
  "scores": {
    "coverage_score":    <0-10>,
    "specificity_score": <0-10>
  },
  "zara_note": "<one short paragraph for Priya in your voice>"
}

SELF-EVALUATION — run before finalising:

Z001: Is primary_gap specific?
Does it name a rule, value, or character?
Bad: 'student missed some rules'
Good: 'welcome bonus completely missing — Rahul mentioned Rs 5,000 for new joiners but student never addressed this'
If bad: rewrite.

Z002: Does zara_note give Priya enough context to ask one targeted Socratic question?
Does it state what was right AND what was missed AND why?
If no: rewrite.

Z003: Is score calibrated?
Not 0 unless attempt is empty. Not 10 unless everything is correct. Proportional to actual coverage.
If not: recalculate.

Z004: Did you reveal the fix?
Check for: 'should return X', 'the fix is', 'student needs to add'.
If yes: rewrite removing the answer.

Z005: Is gaps_covered evidenced?
Can you quote the student's attempt for every item in gaps_covered?
If not: move to gaps_missing.

Z006: Are edge cases genuine?
Are they realistic? Could student have anticipated them?
If not: remove them.

Only output when all 6 pass. Maximum 3 retries.
"""


# Per-exercise framing. Tells Zara what KIND of artifact the student submitted
# so she scores against the skill that matters for that exercise type.
EXERCISE_TYPE_FRAMING = {
    1: "EXERCISE TYPE 1 — PROMPT AI TO BUILD. Student wrote a natural-language prompt instructing the AI to build the function from scratch. Score Requirement Completeness + Edge Case Thinking primarily; output verification is secondary.",
    2: "EXERCISE TYPE 2 — DECOMPOSE. Student submitted a list of sub-tasks. Score Problem Decomposition primarily — did they break the task into the right ordered steps an AI can execute one at a time?",
    3: "EXERCISE TYPE 3 — PREDICT AI FAILURE. Student was shown a deliberately-flawed prompt and listed which categories of input would break it. Score Edge Case Thinking + Output Verification primarily — did they spot the categories the flawed prompt missed?",
    4: "EXERCISE TYPE 4 — VERIFY. Student wrote test cases against AI-generated code that looks plausible. Score Output Verification primarily — did their tests probe the dimensions that would expose hidden bugs?",
    5: "EXERCISE TYPE 5 — IMPROVE AFTER FAILURE. Student saw a failing prompt + its failures and submitted a tightened revised prompt. Score Iterative Refinement primarily — did they use the failure evidence to add the specific missing constraints, rather than rewriting vaguely?",
}


def _framing_for(exercise_type: Optional[int]) -> str:
    if exercise_type is None:
        return ""
    return EXERCISE_TYPE_FRAMING.get(int(exercise_type), "")


# JSON extraction is shared via backend.core.llm.extract_json.
_extract_json = extract_json


@dataclass
class AssessmentResult:
    # v4 schema fields. `gaps_missing` replaces legacy `gaps` (kept as alias).
    gaps: list[str]                # alias for gaps_missing — kept for back-compat
    gaps_covered: list[str]        # gaps the student DID cover in their attempt
    gaps_missing: list[str]        # gaps the student MISSED (drove the failure)
    omissions: list[str]           # things the spec required that the student left out
    commissions: list[str]         # things the student added that spec did not ask for
    requirement_quality: float     # 0-10, LLM-judged precision + completeness
    output_quality: float          # 0-10, deterministic (10 * pass rate)
    overall_score: float           # 0-10, weighted
    primary_gap: Optional[str]     # the single most important missing gap
    zara_note: str                 # Coach-only — never shown to student
    raw_response: str              # for debugging
    input_tokens: int
    output_tokens: int
    # v5: per-exercise scoring detail. Keys vary by exercise_type — see
    # SYSTEM_PROMPT for the schema. Always populated (empty dict if the
    # LLM omits it).
    type_specific: dict[str, Any] = field(default_factory=dict)
    # Type-4 specific: true when student wrote test cases whose expected
    # values happen to match the buggy code's output (i.e. the test was
    # wrong but it "passed" against the buggy implementation).
    accidentally_passing_flag: bool = False
    # Set when Zara cannot confidently grade the attempt (missing context,
    # unparseable LLM output, schema gaps). Frontend surfaces a neutral
    # "QA assessment needs review" message in that case.
    eval_warning: bool = False
    # v6: genuine real-world edge cases Zara identified by reasoning about
    # the generated code + meeting (NOT from a hardcoded list).
    genuine_edge_cases: list[str] = field(default_factory=list)

    # Back-compat properties for callers still using old field names.
    @property
    def requirement_score(self) -> float:
        return self.requirement_quality

    @property
    def output_score(self) -> float:
        return self.output_quality

    @property
    def reasoning(self) -> str:
        return self.zara_note


def _format_failing_tests(execution: ExecutionResult, limit: int = 12) -> str:
    if execution.setup_error:
        return f"SETUP ERROR — code did not run at all: {execution.setup_error}"
    if execution.timed_out:
        return "TIMEOUT — code ran past the time limit (probable infinite loop)."
    failures = [o for o in execution.outcomes if not o.passed]
    if not failures:
        return "All tests passed."
    lines = []
    for o in failures[:limit]:
        err = f"  error={o.error}" if o.error else ""
        lines.append(
            f"  input={o.input!r:>18}  expected={o.expected!r:<6}  actual={o.actual!r:<6}{err}"
        )
    if len(failures) > limit:
        lines.append(f"  ... and {len(failures) - limit} more failing cases")
    return "FAILING TESTS:\n" + "\n".join(lines)


def _format_gap_taxonomy(question: dict[str, Any]) -> str:
    items = question.get("gap_taxonomy") or []
    if not items:
        return "GAP TAXONOMY: (none provided for this question)"
    lines = ["GAP TAXONOMY (pick one key, or null):"]
    for it in items:
        lines.append(f"  - key: {it['key']}")
        lines.append(f"    skill: {it.get('skill', '?')}")
        lines.append(f"    description: {it['description']}")
    return "\n".join(lines)


_ASSESSOR_SUBMISSION_LABELS = {
    1: "STUDENT'S PROMPT (natural-language instruction to AI)",
    2: "STUDENT'S DECOMPOSITION (sub-tasks they listed)",
    3: "STUDENT'S IDENTIFIED GAPS (what they spotted in the flawed prompt)",
    4: "STUDENT'S TEST CASES (the (input, expected) pairs they wrote)",
    5: "STUDENT'S REVISED PROMPT (their tightened prompt after the failure)",
}


def _format_generated_code(code: Optional[str]) -> str:
    if not code:
        return ""
    return "GENERATED_CODE (AI translated the student's prompt to Python — reason about this directly):\n" + str(code).strip()


def _format_meeting_script(question: dict[str, Any], limit: int = 12) -> str:
    items = question.get("meeting_script") or []
    if not items:
        return "MEETING_SCRIPT: (no briefing on file)"
    lines = ["MEETING_SCRIPT (what was actually said in the meeting):"]
    for entry in items[:limit]:
        if not isinstance(entry, dict):
            continue
        who = entry.get("name") or entry.get("character") or "?"
        role = entry.get("role") or ""
        msg = (entry.get("message") or "").strip()
        head = f"{who} ({role})" if role else who
        lines.append(f"  [{head}]: {msg}")
    return "\n".join(lines)


def _format_reference_section(question: dict[str, Any], exercise_type: Optional[int]) -> str:
    """Type-specific reference block — solution / decomposition / failure
    cases / bugs — whichever the question file defines.
    """
    parts: list[str] = []
    ref_sol = question.get("reference_solution") or question.get("reference_code")
    if ref_sol:
        parts.append("REFERENCE_SOLUTION (ground truth code — student NEVER sees):")
        parts.append(str(ref_sol).strip())

    if exercise_type == 2:
        decomp = question.get("reference_decomposition")
        if isinstance(decomp, list) and decomp:
            parts.append("")
            parts.append("REFERENCE_DECOMPOSITION (the precise sub-tasks Zara expects):")
            for d in decomp:
                if isinstance(d, dict):
                    parts.append(f"  - {d.get('description') or d.get('key') or d}")
                else:
                    parts.append(f"  - {d}")

    if exercise_type == 3:
        cases = question.get("reference_failure_cases")
        if isinstance(cases, list) and cases:
            parts.append("")
            parts.append("REFERENCE_FAILURE_CASES (the gaps the flawed code actually has):")
            for c in cases:
                if isinstance(c, dict):
                    parts.append(f"  - {c.get('description') or c.get('key') or c}")
                else:
                    parts.append(f"  - {c}")

    if exercise_type == 4:
        bugs = question.get("reference_bugs")
        if isinstance(bugs, list) and bugs:
            parts.append("")
            parts.append("REFERENCE_BUGS (the bugs the buggy code actually has):")
            for b in bugs:
                if isinstance(b, dict):
                    parts.append(f"  - {b.get('description') or b.get('key') or b}")
                else:
                    parts.append(f"  - {b}")

    return "\n".join(parts) if parts else "(no reference material on file)"


def build_user_message(
    student_prompt: str,
    question: dict[str, Any],
    execution: ExecutionResult,
    exercise_type: Optional[int] = None,
    *,
    generated_code: Optional[str] = None,
    type4_context: Optional[dict[str, Any]] = None,   # kept for back-compat (unused)
    type5_context: Optional[dict[str, Any]] = None,   # kept for back-compat (unused)
) -> str:
    """v6 — Zara now reasons about meeting + generated_code + student attempt
    only. No real_gaps, no reference_solution, no hidden_tests context.
    Surface fields (ai_code_shown, buggy_ai_code, original_broken_prompt,
    broken_code_produced) ARE included because they are what the student
    was looking at when they wrote their attempt.
    """
    label = _ASSESSOR_SUBMISSION_LABELS.get(int(exercise_type)) if exercise_type else "STUDENT'S PROMPT"
    parts = []
    framing = _framing_for(exercise_type)
    if framing:
        parts.append(framing)
        parts.append("")
    parts.extend([
        f"STUDENT_ATTEMPT — {label}:",
        student_prompt.strip(),
        "",
        _format_meeting_script(question),
    ])

    # Type 1 / Type 5 — include the AI-generated code Zara should reason about.
    if exercise_type in (1, 5) and generated_code:
        parts.append("")
        parts.append(_format_generated_code(generated_code))

    # Type 3 — student is looking at a flawed prompt + the code it produced.
    if exercise_type == 3:
        ai_prompt = question.get("ai_prompt_shown") or question.get("flawed_prompt")
        ai_code = question.get("ai_code_shown") or question.get("target_code")
        if ai_prompt:
            parts.append("")
            parts.append("AI_PROMPT_SHOWN (what the previous developer wrote):")
            parts.append(str(ai_prompt).strip())
        if ai_code:
            parts.append("")
            parts.append("AI_CODE_SHOWN (the code AI produced from that prompt — student is hunting for failure cases here):")
            parts.append(str(ai_code).strip())

    # Type 4 — student is writing test cases against this buggy code.
    if exercise_type == 4:
        buggy = question.get("buggy_ai_code") or question.get("target_code")
        if buggy:
            parts.append("")
            parts.append("BUGGY_AI_CODE (the implementation under test — student writes test cases against this):")
            parts.append(str(buggy).strip())

    # Type 5 — student is fixing a broken prompt; show the broken context.
    if exercise_type == 5:
        broken_prompt = question.get("original_broken_prompt") or question.get("failing_prompt")
        broken_code = question.get("broken_code_produced")
        failed_shown = question.get("failed_tests_shown") or []
        if broken_prompt:
            parts.append("")
            parts.append("ORIGINAL_BROKEN_PROMPT (what failed QA — student is fixing this):")
            parts.append(str(broken_prompt).strip())
        if broken_code:
            parts.append("")
            parts.append("BROKEN_CODE_PRODUCED (code from the broken prompt):")
            parts.append(str(broken_code).strip())
        if failed_shown:
            parts.append("")
            parts.append("FAILED_TESTS_SHOWN (what QA caught):")
            for t in failed_shown[:6]:
                parts.append(
                    f"  - input={t.get('input')!r} expected={t.get('expected')!r} actual={t.get('actual')!r}"
                )

    parts.extend([
        "",
        "Reason about the meeting and the student's attempt. Identify gaps_covered, gaps_missing, and the single primary_gap.",
        "Identify genuine_edge_cases the student didn't anticipate. Skip impossible or obscure ones.",
        "Score per the rubric in the system prompt. Run the Z001-Z006 self-evaluation. Return JSON only.",
    ])
    return "\n".join(parts)


def assess(
    student_prompt: str,
    question: dict[str, Any],
    execution: ExecutionResult,
    *,
    exercise_type: Optional[int] = None,
    generated_code: Optional[str] = None,
    type4_context: Optional[dict[str, Any]] = None,   # legacy / unused in v6
    type5_context: Optional[dict[str, Any]] = None,   # legacy / unused in v6
    max_tokens: int = 480,
) -> AssessmentResult:
    """v6 — Zara reasons about meeting + generated_code + student attempt.
    output_quality is now LLM-judged for all types (no hidden tests). The
    `execution` arg is still accepted for back-compat but its pass-rate is
    no longer authoritative for the score.
    """
    if exercise_type is None:
        exercise_type = question.get("exercise_type")

    # Sample-test pass rate is informational only now — kept for UI display
    # of sample test rows; LLM judges the actual output_quality.
    if execution.num_total > 0:
        pass_rate = execution.num_passed / execution.num_total
    else:
        pass_rate = 0.0
    sample_pass_score = round(10.0 * pass_rate, 2)

    user_text = build_user_message(
        student_prompt, question, execution,
        exercise_type=exercise_type,
        generated_code=generated_code,
    )
    result = llm_chat(
        system=SYSTEM_PROMPT,
        user=user_text,
        max_tokens=max_tokens,
        temperature=0.2,
        response_format_json=True,
    )
    raw = result.text

    try:
        parsed = _extract_json(raw)
    except ValueError:
        # If the LLM returned junk, fall back to a neutral, warning-flagged
        # assessment. No deterministic scoring path exists in v6.
        return AssessmentResult(
            gaps=[],
            gaps_covered=[],
            gaps_missing=[],
            omissions=[],
            commissions=[],
            requirement_quality=sample_pass_score,
            output_quality=sample_pass_score,
            overall_score=sample_pass_score,
            primary_gap=None,
            zara_note=f"Assessor LLM returned unparseable output. Raw: {raw[:200]!r}",
            raw_response=raw,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            type_specific={},
            accidentally_passing_flag=False,
            eval_warning=True,
            genuine_edge_cases=[],
        )

    def _str_list(v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if isinstance(x, (str, int, float)) and str(x).strip()]

    gaps_covered = _str_list(parsed.get("gaps_covered"))
    gaps_missing = _str_list(parsed.get("gaps_missing"))
    if not gaps_missing:
        legacy_gaps = _str_list(parsed.get("gaps"))
        gaps_missing = legacy_gaps

    genuine_edge_cases = _str_list(parsed.get("genuine_edge_cases"))

    # primary_gap is a free-text phrase.
    primary_gap = parsed.get("primary_gap")
    if primary_gap is not None and (not isinstance(primary_gap, str) or not primary_gap.strip()):
        primary_gap = None
    if isinstance(primary_gap, str):
        primary_gap = primary_gap.strip() or None

    # Scores — Zara now emits coverage_score + specificity_score only.
    # overall_score is computed in Python, never trusted from the LLM.
    # Legacy field names (requirement_quality / output_quality) accepted
    # as fallback so older question-file or chat fixtures still parse.
    scores_block = parsed.get("scores") if isinstance(parsed.get("scores"), dict) else {}

    def _pick_score(primary: str, fallback: str, default: float = 0.0) -> float:
        val = scores_block.get(primary,
              scores_block.get(fallback,
              parsed.get(primary,
              parsed.get(fallback, default))))
        try:
            return max(0.0, min(10.0, float(val)))
        except (TypeError, ValueError):
            return default

    coverage_score = _pick_score("coverage_score", "requirement_quality")
    specificity_score = _pick_score("specificity_score", "output_quality")

    # Computed — never read from LLM output.
    overall_score = round((coverage_score + specificity_score) / 2.0, 1)

    # Keep AssessmentResult / RunResponse field names stable so the
    # frontend ZaraCard + downstream code don't have to change. Coverage
    # maps to requirement_quality, specificity maps to output_quality.
    requirement_quality = coverage_score
    output_quality = specificity_score

    omissions = _str_list(parsed.get("omissions"))
    commissions = _str_list(parsed.get("commissions"))

    zara_note = str(parsed.get("zara_note") or parsed.get("reasoning") or "").strip()
    if not zara_note:
        zara_note = "(no note provided)"

    eval_warning = bool(parsed.get("eval_warning", False))
    # v6: type_specific + accidentally_passing_flag dropped per spec. Kept on
    # the dataclass for back-compat with the public RunResponse builder, but
    # always empty/false now.
    type_specific_raw: dict[str, Any] = {}
    accidentally_passing_flag = False

    return AssessmentResult(
        gaps=gaps_missing,            # alias for gaps_missing
        gaps_covered=gaps_covered,
        gaps_missing=gaps_missing,
        omissions=omissions,
        commissions=commissions,
        requirement_quality=round(requirement_quality, 2),
        output_quality=round(output_quality, 2),
        overall_score=round(overall_score, 2),
        primary_gap=primary_gap,
        zara_note=zara_note,
        raw_response=raw,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        type_specific=type_specific_raw,
        accidentally_passing_flag=accidentally_passing_flag,
        genuine_edge_cases=genuine_edge_cases,
        eval_warning=eval_warning,
    )


__all__ = ["assess", "AssessmentResult", "SYSTEM_PROMPT"]
