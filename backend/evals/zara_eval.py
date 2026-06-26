"""Zara Assessor Agent — automated eval set.

Codifies the Z001-Z006 self-evaluation block from Zara's system prompt as
an external, testable harness. The runner re-prompts Zara up to
`MAX_RETRIES` times when any criterion fails. After the cap, the last
attempt is returned along with a report flagging which checks still failed
(no infinite loop).

The eval set is intentionally a MIX of deterministic checks (cheap, fast,
no LLM call) and LLM-judged checks (for qualitative criteria where regex
or rules can't capture intent). Deterministic checks run first — if they
fail, the LLM judge is skipped for that round (no wasted tokens).

Each criterion documents:
  - id              short stable identifier (Z001 etc.)
  - principle       one-line statement of what's being checked
  - bad_example     what failure looks like
  - good_example    what success looks like
  - check_kind      "deterministic" or "llm"
  - check(...)      returns (passed, reason)

Add a new criterion by appending to CRITERIA. The runner picks it up
automatically. Mark check_kind correctly — LLM checks cost ~1 call each
per retry, so prefer deterministic when possible.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backend.agents.assessor import AssessmentResult, assess
from backend.core.code_generator import generate_code
from backend.core.code_executor import ExecutionResult, execute
from backend.core.llm import LLMError, chat as llm_chat, extract_json
from backend.core.question_loader import (
    function_name_from_signature,
    load_question,
)


logger = logging.getLogger("nxtcorp.evals.zara")


# ============================================================================
# CRITERIA
# ============================================================================


@dataclass
class ZaraCriterion:
    """A single eval check against a Zara AssessmentResult."""

    id: str
    name: str
    principle: str
    bad_example: str
    good_example: str
    check_kind: str   # "deterministic" | "llm"
    check: Callable[[AssessmentResult, dict[str, Any], str], tuple[bool, str]]


# ---------- Deterministic checks ----------


def _check_z001_primary_gap_specific(
    a: AssessmentResult, question: dict[str, Any], student_prompt: str,
) -> tuple[bool, str]:
    """Z001 — primary_gap must NAME a rule, value, or character.
    Vague phrasing ("student missed some rules") fails.
    """
    pg = (a.primary_gap or "").strip()
    if not pg:
        return False, "primary_gap is empty"
    if len(pg) < 25:
        return False, f"primary_gap too short ({len(pg)} chars) — likely too vague"
    vague_markers = (
        "some rules", "various", "things", "stuff", "general", "many gaps",
        "didn't cover", "needs improvement", "not specific",
    )
    pg_lower = pg.lower()
    if any(m in pg_lower for m in vague_markers):
        return False, f"primary_gap contains vague marker — needs to name a specific rule/value/character"
    # Bonus signal: references a character (Rahul/Sneha/...) or a number.
    has_signal = bool(re.search(r"\b(Rahul|Sneha|Vikram|Ananya|Rs\s*\d|days|percent|%|\d)", pg, re.IGNORECASE))
    if not has_signal:
        return True, "passes basic shape check but no character/number signal — borderline"
    return True, "names a specific rule/value/character"


def _check_z003_score_calibrated(
    a: AssessmentResult, question: dict[str, Any], student_prompt: str,
) -> tuple[bool, str]:
    """Z003 — scores must be in [0, 10] and not extreme unless justified."""
    for key, val in (
        ("requirement_quality", a.requirement_quality),
        ("output_quality", a.output_quality),
        ("overall_score", a.overall_score),
    ):
        if val is None or not (0.0 <= float(val) <= 10.0):
            return False, f"{key}={val} out of [0,10]"
    # Score = 0 only if attempt is genuinely empty.
    if a.overall_score == 0.0 and student_prompt.strip():
        return False, "overall_score=0 but student attempt is non-empty"
    # Score = 10 only if no gaps_missing and primary_gap is None.
    if a.overall_score >= 9.9 and (a.gaps_missing or a.primary_gap):
        return False, "overall_score≈10 but gaps_missing or primary_gap is set"
    return True, "scores in range and proportional"


def _check_z004_no_fix_revealed(
    a: AssessmentResult, question: dict[str, Any], student_prompt: str,
) -> tuple[bool, str]:
    """Z004 — zara_note must NOT reveal the fix / correct value / action."""
    note = (a.zara_note or "").lower()
    if not note:
        return True, "empty note (will fail Z002 instead)"
    fix_markers = (
        "should return ",
        "the fix is",
        "the answer is",
        "student needs to add",
        "student should add",
        "needs to specify that",
        "must return ",
        "the correct value is",
        "the correct return is",
        "the function should",
    )
    hits = [m for m in fix_markers if m in note]
    if hits:
        return False, f"zara_note reveals the fix via phrase(s): {hits}"
    return True, "no fix-revealing phrase found"


def _check_z005_gaps_covered_non_empty_when_score_high(
    a: AssessmentResult, question: dict[str, Any], student_prompt: str,
) -> tuple[bool, str]:
    """Z005 — gaps_covered must have items when requirement_quality is high
    (≥6). Empty gaps_covered + high requirement = unevidenced score.
    """
    if a.requirement_quality >= 6.0 and not a.gaps_covered:
        return False, (
            f"requirement_quality={a.requirement_quality:.1f} ≥ 6.0 but "
            "gaps_covered is empty — can't evidence what was covered"
        )
    return True, "gaps_covered evidenced (or score appropriately low)"


# ---------- LLM-judged checks ----------


_LLM_JUDGE_SYSTEM = """You are a strict evaluator for Zara Khan's QA assessments. You check ONE criterion at a time. Return JSON only:

{"passed": true | false, "reason": "<one short sentence>"}

Be strict but fair. Pass only when the criterion is genuinely met.
"""


def _llm_judge(criterion_id: str, principle: str, prompt_body: str) -> tuple[bool, str]:
    """Run a single LLM-judge call for an Zara criterion."""
    user = (
        f"CRITERION {criterion_id}: {principle}\n\n"
        f"{prompt_body}\n\n"
        "Does Zara's output satisfy this criterion? Return JSON only."
    )
    try:
        result = llm_chat(
            system=_LLM_JUDGE_SYSTEM,
            user=user,
            max_tokens=120,
            temperature=0.1,
            response_format_json=True,
        )
        parsed = extract_json(result.text)
        passed = bool(parsed.get("passed", False))
        reason = str(parsed.get("reason", "(no reason)")).strip()
        return passed, reason
    except (LLMError, ValueError) as e:
        # If the judge itself errors, default to PASS (don't block the
        # student on infra issues). Surface in the report.
        return True, f"(judge skipped — {type(e).__name__})"


def _check_z002_note_actionable(
    a: AssessmentResult, question: dict[str, Any], student_prompt: str,
) -> tuple[bool, str]:
    """Z002 — zara_note gives Priya enough context to ask one targeted
    Socratic question. Should state what was RIGHT, what was MISSED, and
    WHY this matters.
    """
    body = (
        f"zara_note:\n{a.zara_note}\n\n"
        f"primary_gap: {a.primary_gap}\n"
        f"gaps_covered: {a.gaps_covered}\n"
        f"gaps_missing: {a.gaps_missing}"
    )
    return _llm_judge(
        "Z002",
        "zara_note must give Priya enough context to ask ONE targeted Socratic "
        "question. It should state what the student got right, what was missed, "
        "and WHY this matters for the task — without revealing the fix.",
        body,
    )


def _check_z006_edge_cases_genuine(
    a: AssessmentResult, question: dict[str, Any], student_prompt: str,
) -> tuple[bool, str]:
    """Z006 — genuine_edge_cases must be realistic + something the student
    could have anticipated from the meeting. Impossible scenarios (zero
    salary, negative years) fail.
    """
    if not a.genuine_edge_cases:
        return True, "no edge cases proposed (vacuous pass)"
    script_lines = []
    for entry in (question.get("meeting_script") or [])[:8]:
        if isinstance(entry, dict):
            script_lines.append(f"- {entry.get('name', '?')}: {entry.get('message', '')}")
    body = (
        f"genuine_edge_cases:\n" + "\n".join(f"  - {e}" for e in a.genuine_edge_cases) +
        "\n\nMEETING_SCRIPT:\n" + "\n".join(script_lines)
    )
    return _llm_judge(
        "Z006",
        "Every edge case must be (a) realistic — could actually happen in real "
        "business data; (b) something the student could have anticipated from "
        "the meeting. Impossible scenarios (zero salary, negative years, "
        "obscure unicode) FAIL this criterion.",
        body,
    )


# ---------- Criteria registry ----------


CRITERIA: list[ZaraCriterion] = [
    ZaraCriterion(
        id="Z001",
        name="primary_gap is specific",
        principle="primary_gap must name a rule, value, or character — never vague phrasing",
        bad_example="student missed some rules",
        good_example=(
            "welcome bonus completely missing — Rahul mentioned Rs 5,000 for "
            "new joiners but student never addressed this"
        ),
        check_kind="deterministic",
        check=_check_z001_primary_gap_specific,
    ),
    ZaraCriterion(
        id="Z002",
        name="zara_note is actionable",
        principle="zara_note must give Priya enough context to ask ONE targeted Socratic question (state right + missed + why)",
        bad_example="Student's prompt was incomplete and missed several things.",
        good_example=(
            "Bonus formula and eligibility are correct. Cap constraint mentioned "
            "but action not specified — AI has no instruction on what to return "
            "when bonus exceeds Rs 50,000. Sneha was explicit about the cap in "
            "the meeting."
        ),
        check_kind="llm",
        check=_check_z002_note_actionable,
    ),
    ZaraCriterion(
        id="Z003",
        name="scores calibrated",
        principle="scores in [0,10]; not 0 unless empty; not 10 unless everything correct; proportional to coverage",
        bad_example="requirement_quality=0.0 on a non-empty attempt with one gap",
        good_example="requirement_quality=6.0 with 3 of 5 rules covered precisely",
        check_kind="deterministic",
        check=_check_z003_score_calibrated,
    ),
    ZaraCriterion(
        id="Z004",
        name="no fix revealed",
        principle="zara_note must NOT state the fix, correct value, or required code",
        bad_example="Student should return 50000 when bonus exceeds the cap.",
        good_example="Cap mentioned but action not specified — gap is around what to return when bonus exceeds the limit.",
        check_kind="deterministic",
        check=_check_z004_no_fix_revealed,
    ),
    ZaraCriterion(
        id="Z005",
        name="gaps_covered is evidenced",
        principle="when requirement_quality ≥ 6, gaps_covered must be non-empty (proves the score)",
        bad_example="requirement_quality=8 with gaps_covered=[]",
        good_example="requirement_quality=8 with gaps_covered=['eligibility rule', 'percentage formula']",
        check_kind="deterministic",
        check=_check_z005_gaps_covered_non_empty_when_score_high,
    ),
    ZaraCriterion(
        id="Z006",
        name="edge cases are genuine",
        principle="genuine_edge_cases must be realistic AND anticipatable from the meeting",
        bad_example="genuine_edge_cases=['zero salary', 'negative years employed']",
        good_example="genuine_edge_cases=['employee on exact 1-year anniversary', 'bonus calculation when basic salary is at the cap threshold']",
        check_kind="llm",
        check=_check_z006_edge_cases_genuine,
    ),
]


# ============================================================================
# RUNNER
# ============================================================================


MAX_RETRIES = 3   # hard ceiling — agent does NOT loop infinitely


@dataclass
class ZaraEvalReport:
    """Telemetry from running the eval set against one assessment.

    `attempts` lists per-retry results so the operator can see whether the
    agent improved or kept missing the same criterion.
    """

    final_assessment: AssessmentResult
    attempts: list[dict[str, Any]] = field(default_factory=list)
    passed_all: bool = False
    failed_criteria: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Zara eval — passed_all={self.passed_all} after {len(self.attempts)} attempt(s)",
        ]
        for i, att in enumerate(self.attempts, start=1):
            ok = "OK" if att.get("passed_all") else "FAIL"
            failed = att.get("failed", [])
            lines.append(f"  attempt {i}: {ok} failed={failed!r}")
        if self.failed_criteria:
            lines.append(f"  STILL FAILING after retries: {self.failed_criteria!r}")
        lines.append(f"  primary_gap: {self.final_assessment.primary_gap!r}")
        lines.append(f"  overall_score: {self.final_assessment.overall_score}")
        return "\n".join(lines)


class ZaraEvalRunner:
    """Run Zara on a (question, student_prompt) pair, evaluate the output
    against CRITERIA, and re-run with feedback up to MAX_RETRIES times.

    Designed to NEVER loop infinitely: cap is enforced; on cap exhaustion
    the most recent assessment is returned with a report flagging which
    criteria still fail.
    """

    def __init__(self, max_retries: int = MAX_RETRIES) -> None:
        self.max_retries = max_retries

    def run(
        self,
        question: dict[str, Any],
        student_prompt: str,
        exercise_type: int,
        generated_code: Optional[str] = None,
        execution: Optional[ExecutionResult] = None,
    ) -> ZaraEvalReport:
        report = ZaraEvalReport(final_assessment=None)  # type: ignore[arg-type]
        exec_ = execution or ExecutionResult(outcomes=[])
        feedback_notes: list[str] = []

        for attempt_idx in range(1, self.max_retries + 1):
            # On retries, fold the prior failure reasons into the student
            # prompt so Zara sees them via the build_user_message channel.
            augmented_prompt = student_prompt
            if feedback_notes:
                augmented_prompt = (
                    student_prompt
                    + "\n\n[EVAL FEEDBACK FROM PRIOR ATTEMPT — improve these specifically:\n"
                    + "\n".join(f"  - {n}" for n in feedback_notes)
                    + "\n]"
                )

            try:
                assessment = assess(
                    augmented_prompt, question, exec_,
                    exercise_type=exercise_type,
                    generated_code=generated_code,
                )
            except LLMError as e:
                logger.error("Zara LLM error on attempt %d: %s", attempt_idx, e)
                # Return whatever we have. Eval can't proceed without an output.
                if report.final_assessment is None:
                    raise
                break

            report.final_assessment = assessment

            # Run every criterion. Collect failures.
            attempt_record: dict[str, Any] = {
                "attempt": attempt_idx,
                "passed": [],
                "failed": [],
                "reasons": {},
            }
            failure_feedback: list[str] = []
            for crit in CRITERIA:
                try:
                    passed, reason = crit.check(assessment, question, student_prompt)
                except Exception as e:
                    # Don't let a buggy check break the loop.
                    passed = True
                    reason = f"(check raised {type(e).__name__}: {e}; defaulting pass)"
                attempt_record["reasons"][crit.id] = reason
                if passed:
                    attempt_record["passed"].append(crit.id)
                else:
                    attempt_record["failed"].append(crit.id)
                    failure_feedback.append(f"{crit.id} ({crit.name}): {reason}")
            attempt_record["passed_all"] = not attempt_record["failed"]
            report.attempts.append(attempt_record)

            if not attempt_record["failed"]:
                report.passed_all = True
                report.failed_criteria = []
                return report

            # Hard cap: don't retry past max_retries.
            if attempt_idx >= self.max_retries:
                report.passed_all = False
                report.failed_criteria = attempt_record["failed"]
                return report

            # Carry failures into next attempt's prompt.
            feedback_notes = failure_feedback

        # Loop exit fallback (shouldn't usually hit this).
        report.failed_criteria = (
            report.attempts[-1]["failed"] if report.attempts else []
        )
        report.passed_all = not report.failed_criteria
        return report


# ============================================================================
# CLI — ad-hoc testing
# ============================================================================


def _run_cli() -> int:
    p = argparse.ArgumentParser(description="Run the Zara eval set against a question + student prompt.")
    p.add_argument("--question", required=True, help="e.g. p001_bonus_calculator")
    p.add_argument("--prompt", required=True, help="student prompt text")
    p.add_argument("--exercise-type", type=int, default=1, choices=[1, 2, 3, 4, 5])
    p.add_argument("--max-retries", type=int, default=MAX_RETRIES)
    args = p.parse_args()

    question = load_question(args.question)

    # For T1/T5 also produce generated_code so Zara has it to reason about.
    generated_code = None
    execution = None
    if args.exercise_type in (1, 5):
        try:
            fn_name = function_name_from_signature(question)
        except ValueError:
            fn_name = None
        gen = generate_code(args.prompt, question)
        generated_code = gen.code
        sample_tests = list(question.get("sample_tests") or [])
        if sample_tests and fn_name:
            execution = execute(generated_code, fn_name, sample_tests, timeout_seconds=5)

    runner = ZaraEvalRunner(max_retries=args.max_retries)
    report = runner.run(
        question=question,
        student_prompt=args.prompt,
        exercise_type=args.exercise_type,
        generated_code=generated_code,
        execution=execution,
    )
    print(report.summary())
    print()
    print("=== FINAL ASSESSMENT ===")
    print(f"primary_gap:    {report.final_assessment.primary_gap}")
    print(f"gaps_covered:   {report.final_assessment.gaps_covered}")
    print(f"gaps_missing:   {report.final_assessment.gaps_missing}")
    print(f"genuine_edges:  {report.final_assessment.genuine_edge_cases}")
    print(f"requirement_q:  {report.final_assessment.requirement_quality}")
    print(f"output_quality: {report.final_assessment.output_quality}")
    print(f"overall_score:  {report.final_assessment.overall_score}")
    print(f"zara_note:      {report.final_assessment.zara_note}")
    return 0 if report.passed_all else 2


if __name__ == "__main__":
    sys.exit(_run_cli())
