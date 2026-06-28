"""Priya Coach Agent — automated eval set.

Codifies Priya's coaching invariants as an external automated harness.
11 criteria — mix of deterministic + LLM judge.

  P001  addresses by name              deterministic
  P002  no answer revealed             LLM judge (skipped at L4)
  P003  ends with question / L4 reveal deterministic, ladder-aware
  P004  depth matches ladder rubric    LLM judge
  P005  warm tone — no harsh phrasing  deterministic blocklist
  P006  short paragraph                deterministic
  P007  grounded in Zara's finding     LLM judge
  P008  no repeat of prior question    LLM judge (skipped on attempt 1)
  P009  reflects student's attempt     LLM judge
  P010  exactly one question mark      deterministic
  P011  L4 reveal is accurate          LLM judge (L4 only)

Runner re-invokes coach with prior failures injected into the
student_prompt as [EVAL FEEDBACK]. Hard cap MAX_RETRIES=3.

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
    id: str
    name: str
    principle: str
    bad_example: str
    good_example: str
    check_kind: str       # "deterministic" | "llm"
    check: Callable[..., tuple[bool, str]]


# ---------- LLM judge wrapper ----------


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


# ---------- P001 — addresses by name (deterministic) ----------


def _check_p001(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    if not student_name:
        return True, "(no student_name supplied — skip)"
    first = student_name.strip().split()[0]
    if not re.search(rf"\b{re.escape(first)}\b", body, re.IGNORECASE):
        return False, f"never addresses '{first}' by name"
    return True, f"addresses '{first}' by name"


# ---------- P002 — no answer revealed (LLM, skip L4) ----------


_P002_JUDGE_SYSTEM = """You are checking whether a coach's message reveals the answer to a student.

The coach must NOT state:
- The missing rule or constraint by name
- The correct value or threshold
- What the student needs to add or change

Respond ONLY with valid JSON:
{
  "reveals_answer": true,
  "reason": "one sentence — what was revealed, or 'nothing revealed'"
}
"""


def _check_p002(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    if level == 4:
        return True, "L4 — reveal is permitted (P011 checks accuracy)"
    user = (
        f"Zara identified this gap:\n\"{assessment.primary_gap}\"\n\n"
        f"Coach message:\n\"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P002_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    reveals = bool(parsed.get("reveals_answer", False))
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if reveals:
        return False, f"reveals answer — {reason}"
    return True, "no reveal"


# ---------- P003 — ends with question / L4 reveal+why (deterministic) ----------


def _check_p003(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    text = body.rstrip()
    if level in (0, 1, 2, 3):
        if not text.endswith("?"):
            return False, f"L{level} reply doesn't end with '?'"
        return True, f"L{level} ends with a question"
    # L4
    has_question = "?" in text
    why_markers = ("why", "why does", "why do you think", "in your own words")
    has_why = any(m in text.lower() for m in why_markers)
    if not (has_question and has_why):
        return False, "L4 must contain reveal AND a 'why does this matter' question"
    return True, "L4 reveals + asks why"


# ---------- P004 — depth matches ladder rubric (LLM) ----------


_P004_JUDGE_SYSTEM = """You are checking whether a coach's message matches the required depth for its ladder level.

Level definitions:
- L1: Conceptual nudge only. Points toward the general area of the gap. Must NOT name the character, rule, or constraint involved.
- L2: Specific direction. Names the character OR the rule category. Does not state the value.
- L3: Concrete pointer. Names both character and rule. Stops just short of the exact value or fix.
- L4: Full reveal. States exactly what was missing — character, rule, and value all present.

Respond ONLY with valid JSON:
{
  "level_matches": true,
  "actual_depth": "too shallow / correct / too deep",
  "reason": "one sentence explaining the verdict"
}
"""


def _check_p004(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    user = (
        f"Ladder level: L{level}\n"
        f"Zara's primary gap: \"{assessment.primary_gap}\"\n"
        f"Coach message: \"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P004_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    matches = bool(parsed.get("level_matches", False))
    actual = parsed.get("actual_depth", "?")
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if not matches:
        return False, f"depth mismatch — judged as {actual}: {reason}"
    return True, f"matches L{level}"


# ---------- P005 — warm tone (deterministic blocklist) ----------


_TONE_BLOCKLIST = (
    "wrong",
    "incorrect",
    "failed",
    "you missed",
    "you forgot",
    "that's not right",
    "thats not right",
    "you didn't",
    "you didnt",
    "you left out",
)


def _check_p005(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    lower = body.lower()
    hits = [m for m in _TONE_BLOCKLIST if m in lower]
    if hits:
        return False, f"harsh phrase(s) detected: {hits}"
    return True, "no harsh phrases"


# ---------- P006 — short paragraph (deterministic) ----------


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _check_p006(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    sentences = _split_sentences(body)
    max_allowed = 4 if level == 4 else 3
    if len(sentences) > max_allowed:
        return False, f"{len(sentences)} sentences > max {max_allowed} for L{level}"
    if "\n\n" in body.strip():
        return False, "contains a paragraph break — must be ONE paragraph"
    if len(body) > 600:
        return False, f"reply too long ({len(body)} chars > 600)"
    return True, f"{len(sentences)} sentence(s), within rhythm"


# ---------- P007 — grounded in Zara's finding (LLM) ----------


_P007_JUDGE_SYSTEM = """You are checking whether a coach's question is about the right gap.

The coach's question must be about the same gap Zara identified — not about a different rule, a different character, or a different part of the task.

Respond ONLY with valid JSON:
{
  "targets_correct_gap": true,
  "reason": "one sentence — what gap the question targets, and whether it matches"
}
"""


def _check_p007(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    if not assessment.primary_gap:
        return True, "(no primary_gap from Zara — skip)"
    user = (
        f"Zara identified this as the primary gap:\n\"{assessment.primary_gap}\"\n\n"
        f"Coach message:\n\"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P007_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    matches = bool(parsed.get("targets_correct_gap", False))
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if not matches:
        return False, f"wrong gap — {reason}"
    return True, "targets correct gap"


# ---------- P008 — no repeat of prior question (LLM, skip attempt 1) ----------


_P008_JUDGE_SYSTEM = """You are checking whether a coach is repeating themselves.

The current message fails if it asks essentially the same question as the previous one — even if the wording is different. A different angle, a different character reference, or a different framing counts as meaningfully different.

Respond ONLY with valid JSON:
{
  "is_repeat": false,
  "reason": "one sentence — what is the same or what changed"
}
"""


def _previous_priya_message(conv: Optional[list[dict[str, str]]]) -> Optional[str]:
    if not conv:
        return None
    for m in reversed(conv):
        if (m.get("character") or "").lower() == "priya":
            body = (m.get("body") or "").strip()
            if body:
                return body
    return None


def _check_p008(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    if attempt_number <= 1:
        return True, "attempt 1 — no prior message to compare"
    prev = _previous_priya_message(conversation_history)
    if not prev:
        return True, "(no prior Priya message found in history)"
    user = (
        f"Previous Priya message for this task:\n\"{prev}\"\n\n"
        f"Current Priya message:\n\"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P008_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    is_repeat = bool(parsed.get("is_repeat", False))
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if is_repeat:
        return False, f"repeats prior question — {reason}"
    return True, "meaningfully different from prior"


# ---------- P009 — reflects student's attempt (LLM) ----------


_P009_JUDGE_SYSTEM = """You are checking whether a coach's message responds to what the student actually wrote.

The coach's message fails if it could have been sent to ANY student regardless of what they wrote. It must acknowledge, reference, or respond to something specific in the student's attempt — either what they got right, how close they came, or the specific gap in their wording.

Respond ONLY with valid JSON:
{
  "reflects_attempt": true,
  "reason": "one sentence — what in the student's attempt is reflected, or why it reads as generic"
}
"""


def _check_p009(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
    student_attempt: str = "",
) -> tuple[bool, str]:
    if not student_attempt.strip():
        return True, "(no student attempt to compare)"
    user = (
        f"Student's attempt:\n\"{student_attempt}\"\n\n"
        f"Coach message:\n\"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P009_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    reflects = bool(parsed.get("reflects_attempt", False))
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if not reflects:
        return False, f"generic — doesn't reflect attempt: {reason}"
    return True, "reflects student's attempt"


# ---------- P010 — exactly one question mark (deterministic) ----------


def _check_p010(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    count = body.count("?")
    if count == 0:
        return False, "no question marks at all"
    if count > 1:
        return False, f"{count} question marks — must be exactly one Socratic question"
    return True, "exactly one question"


# ---------- P011 — L4 reveal is accurate (LLM, L4 only) ----------


_P011_JUDGE_SYSTEM = """You are checking whether a coach's L4 reveal is accurate.

The reveal passes if:
- The rule or constraint Priya names matches what Zara identified
- The value Priya states (if any) matches what Zara reported
- Nothing additional is revealed beyond what Zara flagged

Respond ONLY with valid JSON:
{
  "reveal_is_accurate": true,
  "reason": "one sentence — what matches or what diverges"
}
"""


def _check_p011(
    body: str, level: int, student_name: str,
    attempt_history: list[dict[str, Any]], question: dict[str, Any],
    assessment: AssessmentResult,
    conversation_history: Optional[list[dict[str, str]]] = None,
    attempt_number: int = 1,
) -> tuple[bool, str]:
    if level != 4:
        return True, "non-L4 — P011 only applies at L4"
    if not assessment.primary_gap:
        return True, "(no primary_gap from Zara — skip)"
    user = (
        f"Zara's primary gap:\n\"{assessment.primary_gap}\"\n\n"
        f"Coach message:\n\"{body}\""
    )
    skipped, skip_reason, parsed = _call_llm_judge(_P011_JUDGE_SYSTEM, user)
    if skipped:
        return True, skip_reason
    accurate = bool(parsed.get("reveal_is_accurate", False))
    reason = str(parsed.get("reason", "(no reason)")).strip()
    if not accurate:
        return False, f"reveal inaccurate — {reason}"
    return True, "reveal matches Zara's finding"


# ---------- Criteria registry ----------


CRITERIA: list[PriyaCriterion] = [
    PriyaCriterion(
        id="P001",
        name="addresses by name",
        principle="Student's first name must appear at least once",
        bad_example="Think about what happens when a very high salary is entered.",
        good_example="Devika, think about what happens when a very high salary is entered.",
        check_kind="deterministic",
        check=_check_p001,
    ),
    PriyaCriterion(
        id="P002",
        name="no answer revealed",
        principle="For L1/L2/L3 must not state the missing rule, correct value, or fix",
        bad_example="(L1) Devika, you need to handle the Rs 50,000 cap — add a check that returns 50,000.",
        good_example="(L1) Devika, Sneha mentioned something specific about what should happen when a number gets too large — did that make it into your instructions?",
        check_kind="llm",
        check=_check_p002,
    ),
    PriyaCriterion(
        id="P003",
        name="ends with question (or L4 reveal+why)",
        principle="L1/L2/L3 end with '?'; L4 has reveal AND 'why does this matter' question",
        bad_example="(L1) Devika, think about the cap and what Sneha said about large bonuses.",
        good_example="(L4) Devika, the missing piece was the Rs 50,000 cap. Why do you think this matters?",
        check_kind="deterministic",
        check=_check_p003,
    ),
    PriyaCriterion(
        id="P004",
        name="depth matches ladder rubric",
        principle="Depth matches assigned level (L1 conceptual, L2 names char/rule, L3 concrete pointer, L4 full reveal)",
        bad_example="(L1, too deep) Devika, Sneha mentioned a cap — did you account for that?",
        good_example="(L1) Devika, is there anything a stakeholder said that didn't make it in?",
        check_kind="llm",
        check=_check_p004,
    ),
    PriyaCriterion(
        id="P005",
        name="warm tone — no harsh phrasing",
        principle="No 'wrong', 'incorrect', 'failed', 'you missed', 'you forgot', etc.",
        bad_example="Devika, you missed the cap constraint that Sneha mentioned.",
        good_example="Devika, Sneha mentioned something about large bonuses — did that make it in?",
        check_kind="deterministic",
        check=_check_p005,
    ),
    PriyaCriterion(
        id="P006",
        name="short paragraph",
        principle="≤3 sentences at L1/L2/L3; ≤4 at L4; no paragraph breaks; <600 chars",
        bad_example="Long lecture spanning 5 sentences with a paragraph break.",
        good_example="Devika, Sneha raised a specific constraint — did you give the AI instructions for that case?",
        check_kind="deterministic",
        check=_check_p006,
    ),
    PriyaCriterion(
        id="P007",
        name="grounded in Zara's finding",
        principle="Question targets the gap Zara identified — not a different rule or character",
        bad_example="(Zara flagged cap) Devika, think about who qualifies for a bonus — did you cover all conditions?",
        good_example="(Zara flagged cap) Devika, Sneha raised a constraint about the output — did you instruct the AI on that case?",
        check_kind="llm",
        check=_check_p007,
    ),
    PriyaCriterion(
        id="P008",
        name="no repeat of prior question",
        principle="Current question must be meaningfully different from previous Priya message (skip on attempt 1)",
        bad_example="L2 rewording L1 with no new angle",
        good_example="L2 adds a character name where L1 only pointed at the area",
        check_kind="llm",
        check=_check_p008,
    ),
    PriyaCriterion(
        id="P009",
        name="reflects student's attempt",
        principle="Must reference something specific in the student's attempt — not a generic question",
        bad_example="Devika, think about what Sneha was most concerned about during the meeting.",
        good_example="Devika, you've got eligibility and the percentage right — the missing thing is what to do when the result crosses a threshold Sneha mentioned.",
        check_kind="llm",
        check=_check_p009,
    ),
    PriyaCriterion(
        id="P010",
        name="exactly one question",
        principle="Exactly one '?' in the response — two questions violate single-Socratic-question rule",
        bad_example="Did you capture everything? And what about when the bonus is large?",
        good_example="Devika, Sneha mentioned something about large bonuses — did that make it in?",
        check_kind="deterministic",
        check=_check_p010,
    ),
    PriyaCriterion(
        id="P011",
        name="L4 reveal is accurate",
        principle="At L4 the revealed rule and value must match Zara's primary_gap",
        bad_example="(L4) Devika, the missing piece was the Rs 40,000 cap.",
        good_example="(L4) Devika, the missing piece was the Rs 50,000 cap — why do you think this matters for payroll?",
        check_kind="llm",
        check=_check_p011,
    ),
]


# ============================================================================
# RUNNER
# ============================================================================


MAX_RETRIES = 3   # hard ceiling


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
            lvl = att.get("level", "?")
            lines.append(f"  attempt {i}: {ok} L{lvl} failed={failed!r}")
        if self.failed_criteria:
            lines.append(f"  STILL FAILING after retries: {self.failed_criteria!r}")
        if self.final_reply:
            lines.append(f"  level: L{self.final_reply.escalation_level}")
            lines.append(f"  body:  {self.final_reply.body}")
        return "\n".join(lines)


class PriyaEvalRunner:
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
                    all_passed_override=False,
                )
            except LLMError as e:
                logger.error("Priya LLM error on attempt %d: %s", attempt_idx, e)
                if report.final_reply is None:
                    raise
                break

            report.final_reply = reply
            body = reply.body
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
                    # P009 needs the original student attempt as an extra arg.
                    if crit.id == "P009":
                        passed, reason = crit.check(
                            body, actual_level, student_display_name,
                            attempt_history or [], question, assessment,
                            conversation_history=conversation_history,
                            attempt_number=attempt_number,
                            student_attempt=student_prompt,
                        )
                    else:
                        passed, reason = crit.check(
                            body, actual_level, student_display_name,
                            attempt_history or [], question, assessment,
                            conversation_history=conversation_history,
                            attempt_number=attempt_number,
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

    # Map requested level → attempt_number so coach hits the right rung
    # (without Arjun firing): L1→1, L2→2, L3→4, L4→5.
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
