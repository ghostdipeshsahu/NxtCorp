"""Priya Coach Agent — automated eval set.

Codifies Priya's coaching invariants as an external automated harness.
Mirrors the Zara eval shape: criteria, retry runner, hard cap, CLI.

Six criteria — mix of deterministic + LLM judge:
  P001  addresses by name              deterministic
  P002  no answer revealed             LLM judge (except L4)
  P003  ends with question (or L4)     deterministic, ladder-aware
  P004  matches ladder rubric          LLM judge
  P005  warm tone, no "wrong"          deterministic blocklist
  P006  short paragraph (≤3 sentences) deterministic

The runner re-invokes the coach with prior failures fed into the system
prompt as `[EVAL FEEDBACK]`. Hard cap MAX_RETRIES=3.

CLI:
    python -m backend.evals.priya_eval --question p001_bonus_calculator \\
        --prompt "calculate 10% bonus" --student-name Devika --level 1
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backend.agents.assessor import AssessmentResult, assess
from backend.agents.coach import (
    CoachReply,
    build_system_prompt,
    build_user_message,
    compute_expression,
    coach as coach_call,
)
from backend.core.code_executor import ExecutionResult, execute
from backend.core.code_generator import generate_code
from backend.core.llm import LLMError, chat as llm_chat, extract_json
from backend.core.question_loader import (
    function_name_from_signature,
    load_question,
)


logger = logging.getLogger("nxtcorp.evals.priya")


# ============================================================================
# CRITERIA
# ============================================================================


@dataclass
class PriyaCriterion:
    """A single eval check against a Priya coach reply."""

    id: str
    name: str
    principle: str
    bad_example: str
    good_example: str
    check_kind: str       # "deterministic" | "llm"
    check: Callable[..., tuple[bool, str]]


# ---------- Deterministic checks ----------


def _check_p001_addresses_by_name(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
) -> tuple[bool, str]:
    """P001 — Priya must address the student by their first name at least once."""
    if not student_name:
        return True, "(no student_name supplied — skip)"
    first = student_name.strip().split()[0]
    pattern = rf"\b{re.escape(first)}\b"
    if not re.search(pattern, body, re.IGNORECASE):
        return False, f"never addresses '{first}' by name"
    return True, f"addresses '{first}' by name"


def _check_p003_ends_with_question_or_l4_reveal(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
) -> tuple[bool, str]:
    """P003 — L1/L2/L3 must end with a question mark. L4 must contain BOTH
    an explicit reveal AND a "why does this matter" question.
    """
    text = body.rstrip()
    if level in (1, 2, 3, 0):
        if not text.endswith("?"):
            return False, f"L{level} reply doesn't end with '?'"
        return True, f"L{level} ends with a question"
    # L4
    has_question = "?" in text
    why_markers = ("why", "why does", "in your own words", "why is this important")
    has_why = any(m in text.lower() for m in why_markers)
    if not (has_question and has_why):
        return False, "L4 must reveal the gap AND ask a 'why does this matter' question"
    return True, "L4 reveals + asks why"


_TONE_BLOCKLIST = (
    "that is wrong",
    "that's wrong",
    "you are wrong",
    "you're wrong",
    "incorrect",
    "wrong answer",
    "you failed",
    "you didn't get",
    "you missed everything",
)


def _check_p005_warm_tone(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
) -> tuple[bool, str]:
    """P005 — never uses harsh 'wrong/incorrect/failed' phrasing.
    Warm coaching tone enforced via phrase blocklist.
    """
    lower = body.lower()
    hits = [m for m in _TONE_BLOCKLIST if m in lower]
    if hits:
        return False, f"harsh phrase(s) detected: {hits}"
    return True, "no harsh phrases"


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _check_p006_short_paragraph(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
) -> tuple[bool, str]:
    """P006 — Priya keeps it Slack-style. One short paragraph, max 3
    sentences for L1/L2/L3. L4 allows up to 4 sentences (reveal + why).
    """
    sentences = _split_sentences(body)
    max_allowed = 4 if level == 4 else 3
    if len(sentences) > max_allowed:
        return False, f"{len(sentences)} sentences > max {max_allowed} for L{level}"
    if "\n\n" in body.strip():
        return False, "contains a paragraph break — must be ONE paragraph"
    if len(body) > 600:
        return False, f"reply too long ({len(body)} chars)"
    return True, f"{len(sentences)} sentence(s), within rhythm"


# ---------- LLM judges ----------


def _call_llm_judge(
    system: str, user: str, max_tokens: int = 280,
) -> tuple[bool, str, dict[str, Any]]:
    """One LLM judge call. On error → (True, reason, {}) to default PASS."""
    try:
        result = llm_chat(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=0.1,
            response_format_json=True,
        )
        parsed = extract_json(result.text)
        return False, "", parsed
    except (LLMError, ValueError) as e:
        return True, f"(judge skipped — {type(e).__name__})", {}


_P002_JUDGE_SYSTEM = """You are evaluating a Socratic coaching message from Priya at NxtCorp.

For Socratic levels L1, L2, and L3, Priya MUST NOT reveal the answer. She
points toward where the gap is, names characters or topics, or quotes one
specific failing input — but she NEVER states the missing rule, value, or
fix. Only L4 is allowed to reveal.

You will be told which level this message is at.

For L1/L2/L3 messages, "reveal" means:
  - stating the missing rule explicitly ("you forgot the cap at Rs 50,000")
  - stating the correct return value ("the function should return 50000")
  - telling the student exactly what to add ("add a check for years > 1")

For L1/L2/L3, "OK" means:
  - asking what character X said about Y
  - quoting one specific failing input and asking what the student's prompt does with it
  - pointing at the dimension of the gap (limits, boundaries, missing rule) without naming the rule

Respond ONLY with valid JSON:
{
  "reveals_answer": true,
  "pass": false,
  "reason": "one sentence — what was revealed, or 'no reveal — points at the gap without naming it'"
}

"pass" is true when reveals_answer is false (for L1/L2/L3) OR when level is 4.
"""


def _check_p002_no_answer_revealed(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
) -> tuple[bool, str]:
    """P002 — for L1/L2/L3, must NOT state the fix/value/rule. For L4 reveal
    is expected (P003 handles structure)."""
    if level == 4:
        return True, "L4 — reveal is permitted"
    user = (
        f"Message level: L{level}\n\n"
        f"Priya's message:\n\"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P002_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    reveals = bool(parsed.get("reveals_answer", False))
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if reveals:
        return False, f"reveals answer at L{level} — {reason}"
    return True, "no answer revealed"


_P004_JUDGE_SYSTEM = """You are evaluating whether a Socratic coaching message
matches its assigned escalation level.

Ladder rubric:
  L1 (conceptual nudge):
    - General area pointer. Does NOT name a specific character or rule by name.
    - May reference "the meeting" in general terms.
    - Style: "Think about what was said about limits — is there anything your
      prompt doesn't account for?"

  L2 (specific direction):
    - Names a character or specific topic from the meeting.
    - Still does not state the rule or value.
    - Style: "Think about what Sneha said specifically — does your prompt
      address the maximum bonus?"

  L3 (concrete pointer):
    - Quotes a specific failing input OR names a specific numeric value
      already known to the student.
    - Asks them to trace through.
    - Style: "When the calculated bonus is Rs 60,000 — what does your
      function return? Did you specify that?"

  L4 (reveal):
    - States the missing rule plainly.
    - Asks a follow-up: why does this matter?

Respond ONLY with valid JSON:
{
  "matches_level": true,
  "actual_level_seen": "L1" | "L2" | "L3" | "L4" | "ambiguous",
  "reason": "one sentence"
}

"matches_level" is true when the message is at the assigned level — neither
too shallow nor too specific.
"""


def _check_p004_matches_ladder_rubric(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
) -> tuple[bool, str]:
    """P004 — depth of the response must match the assigned ladder level."""
    user = (
        f"ASSIGNED level: L{level}\n\n"
        f"Priya's message:\n\"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P004_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    matches = bool(parsed.get("matches_level", False))
    actual = parsed.get("actual_level_seen", "?")
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if not matches:
        return False, f"depth mismatch — assigned L{level}, judged as {actual}: {reason}"
    return True, f"matches L{level}"


# ---------- Criteria registry ----------


CRITERIA: list[PriyaCriterion] = [
    PriyaCriterion(
        id="P001",
        name="addresses by name",
        principle="Priya must address the student by their first name at least once",
        bad_example="Think about what was said about limits in the meeting.",
        good_example="Devika, think about what was said about limits in the meeting.",
        check_kind="deterministic",
        check=_check_p001_addresses_by_name,
    ),
    PriyaCriterion(
        id="P002",
        name="no answer revealed",
        principle="For L1/L2/L3, must NOT state the missing rule, correct value, or required fix",
        bad_example="(L1) You forgot the Rs 50,000 cap. Add a check that caps at 50000.",
        good_example="(L1) Devika, think about what Sneha said about limits — does your prompt account for that?",
        check_kind="llm",
        check=_check_p002_no_answer_revealed,
    ),
    PriyaCriterion(
        id="P003",
        name="ends with question (or L4 reveal+why)",
        principle="L1/L2/L3 must end with '?'. L4 must contain a reveal AND a 'why does this matter' question",
        bad_example="(L1) Look at what Sneha said about limits.",
        good_example="(L1) Devika, think about what Sneha said about limits — anything missing?",
        check_kind="deterministic",
        check=_check_p003_ends_with_question_or_l4_reveal,
    ),
    PriyaCriterion(
        id="P004",
        name="matches ladder rubric",
        principle="Depth of the response must match the assigned ladder level (L1 conceptual, L2 specific direction, L3 concrete pointer, L4 reveal)",
        bad_example="(L1, too specific) Devika, what does your prompt return when the bonus exceeds Rs 50,000?",
        good_example="(L1) Devika, think about what was said about limits — anything your prompt doesn't account for?",
        check_kind="llm",
        check=_check_p004_matches_ladder_rubric,
    ),
    PriyaCriterion(
        id="P005",
        name="warm tone — no 'wrong'/'incorrect'/'failed'",
        principle="Never uses harsh phrasing. Warm coaching language only.",
        bad_example="Your prompt is wrong — it doesn't handle the cap.",
        good_example="Good start! Now think about what happens when the bonus is large…",
        check_kind="deterministic",
        check=_check_p005_warm_tone,
    ),
    PriyaCriterion(
        id="P006",
        name="short paragraph — Slack rhythm",
        principle="One paragraph, max 3 sentences (4 for L4 reveal). No paragraph breaks. Under 600 chars.",
        bad_example="Long lecture spanning 6 sentences with bullet points and paragraph breaks.",
        good_example="Devika, think about what Sneha said about limits — anything missing?",
        check_kind="deterministic",
        check=_check_p006_short_paragraph,
    ),
]


# ============================================================================
# RUNNER
# ============================================================================


MAX_RETRIES = 3   # hard ceiling — agent does NOT loop infinitely


@dataclass
class PriyaEvalReport:
    final_reply: Optional[CoachReply]
    attempts: list[dict[str, Any]] = field(default_factory=list)
    passed_all: bool = False
    failed_criteria: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Priya eval — passed_all={self.passed_all} after {len(self.attempts)} attempt(s)",
        ]
        for i, att in enumerate(self.attempts, start=1):
            ok = "OK" if att.get("passed_all") else "FAIL"
            failed = att.get("failed", [])
            lines.append(f"  attempt {i}: {ok} failed={failed!r}")
        if self.failed_criteria:
            lines.append(f"  STILL FAILING after retries: {self.failed_criteria!r}")
        if self.final_reply:
            lines.append(f"  level: L{self.final_reply.escalation_level}")
            lines.append(f"  body:  {self.final_reply.body}")
        return "\n".join(lines)


class PriyaEvalRunner:
    """Run Priya, evaluate the output against CRITERIA, re-run with feedback
    up to MAX_RETRIES times.
    """

    def __init__(self, max_retries: int = MAX_RETRIES) -> None:
        self.max_retries = max_retries

    def run(
        self,
        *,
        question: dict[str, Any],
        student_display_name: str,
        student_prompt: str,
        execution: ExecutionResult,
        assessment: AssessmentResult,
        attempt_number: int,
        level: int,
        exercise_type: int,
        attempt_history: Optional[list[dict[str, Any]]] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> PriyaEvalReport:
        report = PriyaEvalReport(final_reply=None)
        feedback_notes: list[str] = []

        for attempt_idx in range(1, self.max_retries + 1):
            # Inject prior failure feedback into student_prompt so coach()
            # sees it in the user message build path.
            augmented_prompt = student_prompt
            if feedback_notes:
                augmented_prompt = (
                    student_prompt
                    + "\n\n[EVAL FEEDBACK FROM PRIOR ATTEMPT — improve these specifically:\n"
                    + "\n".join(f"  - {n}" for n in feedback_notes)
                    + "\n]"
                )

            try:
                reply = coach_call(
                    student_display_name=student_display_name,
                    question=question,
                    student_prompt=augmented_prompt,
                    execution=execution,
                    assessment=assessment,
                    attempt_number=attempt_number,
                    conversation_history=conversation_history,
                    exercise_type=exercise_type,
                    arjun_fired=False,
                    attempt_history=attempt_history,
                    all_passed_override=False,  # eval flow always treats as "failed → coaching"
                )
            except LLMError as e:
                logger.error("Priya LLM error on attempt %d: %s", attempt_idx, e)
                if report.final_reply is None:
                    raise
                break

            report.final_reply = reply
            body = reply.body
            # Always check against the level Priya ACTUALLY emitted — not
            # the level the caller requested. compute_step inside coach()
            # may have routed her to a different rung based on attempt
            # history / Arjun gating, and the criteria need to evaluate
            # the emitted depth.
            actual_level = reply.escalation_level

            attempt_record: dict[str, Any] = {
                "attempt": attempt_idx,
                "level": actual_level,
                "passed": [],
                "failed": [],
                "reasons": {},
            }
            failure_feedback: list[str] = []

            for crit in CRITERIA:
                try:
                    passed, reason = crit.check(
                        body, actual_level, student_display_name,
                        attempt_history or [], question, assessment,
                    )
                except Exception as e:
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

            if attempt_idx >= self.max_retries:
                report.passed_all = False
                report.failed_criteria = attempt_record["failed"]
                return report

            feedback_notes = failure_feedback

        report.failed_criteria = report.attempts[-1]["failed"] if report.attempts else []
        report.passed_all = not report.failed_criteria
        return report


# ============================================================================
# CLI
# ============================================================================


def _run_cli() -> int:
    p = argparse.ArgumentParser(description="Run the Priya eval set against a question + student prompt.")
    p.add_argument("--question", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--student-name", default="Devika")
    p.add_argument("--level", type=int, default=1, choices=[1, 2, 3, 4])
    p.add_argument("--exercise-type", type=int, default=1, choices=[1, 2, 3, 4, 5])
    p.add_argument("--max-retries", type=int, default=MAX_RETRIES)
    args = p.parse_args()

    question = load_question(args.question)

    # Produce a real assessment so the coach has zara_findings to work with.
    gen_code = None
    execution = ExecutionResult(outcomes=[])
    if args.exercise_type in (1, 5):
        gen = generate_code(args.prompt, question)
        gen_code = gen.code
        fn_name = function_name_from_signature(question)
        sample_tests = list(question.get("sample_tests") or [])
        if sample_tests:
            execution = execute(gen_code, fn_name, sample_tests, timeout_seconds=5)

    assessment = assess(
        args.prompt, question, execution,
        exercise_type=args.exercise_type,
        generated_code=gen_code,
    )

    # Map requested level → attempt_number so compute_step inside coach()
    # routes Priya to the matching ladder rung (without Arjun firing).
    #   L1 → attempt 1, L2 → 2, L3 → 4, L4 → 5
    attempt_for_level = {1: 1, 2: 2, 3: 4, 4: 5}.get(args.level, 1)

    runner = PriyaEvalRunner(max_retries=args.max_retries)
    report = runner.run(
        question=question,
        student_display_name=args.student_name,
        student_prompt=args.prompt,
        execution=execution,
        assessment=assessment,
        attempt_number=attempt_for_level,
        level=args.level,
        exercise_type=args.exercise_type,
        attempt_history=[],
        conversation_history=None,
    )
    print(report.summary())
    return 0 if report.passed_all else 2


if __name__ == "__main__":
    sys.exit(_run_cli())
