"""Step 5 verification — exercise the Coach Agent across the full Socratic ladder.

Five scenarios:
  A) First-attempt pass  -> level 0, expression=excited, no gap name.
  B) Attempt 1 fail      -> L1 conceptual nudge. No specific input quoted. No gap named.
  C) Attempt 2 fail      -> L2 specific direction. Talks about category/dimension, not the rule.
  D) Attempt 3 fail      -> L3 direct hint with ONE specific failing input quoted.
  E) Attempt 4 fail      -> L4 reveal. Names the missing rule plainly. Asks a 'why' question.

We use canned ExecutionResult + AssessmentResult objects so we don't burn credits
re-running steps 3 and 4 just to feed the Coach.

Run from project root:
    python -m scripts.test_step5
"""

from __future__ import annotations

import re
import sys
import textwrap
from typing import Any

# Priya uses emoji in celebrations; Windows default cp1252 console crashes on them.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from backend.agents.assessor import AssessmentResult
from backend.agents.coach import coach
from backend.core.code_executor import ExecutionResult, TestOutcome
from backend.core.question_loader import load_question


# ---------- helpers ----------

def build_outcomes(tests, failing_inputs):
    outcomes = []
    for t in tests:
        passed = t["input"] not in failing_inputs
        actual = t["expected"] if passed else (not t["expected"])
        outcomes.append(
            TestOutcome(input=t["input"], expected=t["expected"], actual=actual, passed=passed, error=None)
        )
    return outcomes


def section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


# Tokens that would betray that internal taxonomy / reference exists.
LEAK_PATTERNS = [
    re.compile(r"primary[_ ]gap", re.IGNORECASE),
    re.compile(r"taxonom", re.IGNORECASE),
    re.compile(r"reference prompt", re.IGNORECASE),
    re.compile(r"hidden test", re.IGNORECASE),
    re.compile(r"reference code", re.IGNORECASE),
    re.compile(r"assessor", re.IGNORECASE),
    re.compile(r"missing_all_lower_case", re.IGNORECASE),
]


def has_leak(body):
    return [p.pattern for p in LEAK_PATTERNS if p.search(body)]


# ---------- main ----------

def main() -> int:
    q = load_question("p001_detect_capital")
    all_tests = list(q["sample_tests"]) + list(q["hidden_tests"])

    # Canned scenario data.
    incomplete_prompt = (
        "Write a Python function named detect_capital that takes a word and returns "
        "True if every character is uppercase, or if the first character is uppercase "
        "and the rest are lowercase. Otherwise return False."
    )
    incomplete_failures = {"a", "ab", "hello", "leetcode"}

    fail_exec = ExecutionResult(outcomes=build_outcomes(all_tests, incomplete_failures))
    fail_assess = AssessmentResult(
        requirement_score=7.5,
        output_score=7.5,
        overall_score=7.5,
        primary_gap="missing_all_lower_case",
        reasoning=(
            "Student covered all-uppercase and title-case but omitted the all-lowercase "
            "rule entirely. All four failing tests are lowercase words. Gap is well-defined."
        ),
        raw_response="",
        input_tokens=0,
        output_tokens=0,
    )

    pass_exec = ExecutionResult(outcomes=build_outcomes(all_tests, set()))
    pass_assess = AssessmentResult(
        requirement_score=10.0,
        output_score=10.0,
        overall_score=10.0,
        primary_gap=None,
        reasoning="Reference-quality prompt. All tests passed.",
        raw_response="",
        input_tokens=0,
        output_tokens=0,
    )

    failing_inputs = {"a", "ab", "hello", "leetcode"}
    overall_ok = True
    summary = []

    def show(label, reply):
        print(f"\n[{label}]")
        print(f"  expression       : {reply.expression}")
        print(f"  escalation_level : {reply.escalation_level}")
        print(f"  tokens           : in={reply.input_tokens} out={reply.output_tokens}")
        print(f"  body:")
        print(textwrap.indent(reply.body, "    "))

    # ---- A. First-try pass: celebration, level 0 ----
    section("A) First-attempt pass — expect level 0, expression=excited")
    a = coach(
        student_display_name="Aarav",
        question=q,
        student_prompt=q["reference_prompt"],
        execution=pass_exec,
        assessment=pass_assess,
        attempt_number=1,
    )
    show("A", a)
    leaks = has_leak(a.body)
    if a.escalation_level != 0:
        print(f"  --> FAIL: level should be 0, got {a.escalation_level}"); overall_ok = False
    if a.expression != "excited":
        print(f"  --> FAIL: expression should be 'excited', got {a.expression!r}"); overall_ok = False
    if leaks:
        print(f"  --> FAIL: internal terms leaked: {leaks}"); overall_ok = False
    summary.append(("A first-try pass", a))

    # ---- B. Attempt 1 fail: L1 conceptual nudge ----
    section("B) Attempt 1 fail — expect L1 (conceptual, no specific input quoted)")
    b = coach(
        student_display_name="Aarav",
        question=q,
        student_prompt=incomplete_prompt,
        execution=fail_exec,
        assessment=fail_assess,
        attempt_number=1,
    )
    show("B", b)
    leaks = has_leak(b.body)
    if b.escalation_level != 1:
        print(f"  --> FAIL: level should be 1, got {b.escalation_level}"); overall_ok = False
    if b.expression != "concerned":
        print(f"  --> FAIL: expression should be 'concerned'"); overall_ok = False
    if leaks:
        print(f"  --> FAIL: internal terms leaked: {leaks}"); overall_ok = False
    # L1 must not quote a specific failing input
    quoted_inputs = [inp for inp in failing_inputs if f"'{inp}'" in b.body or f'"{inp}"' in b.body]
    if quoted_inputs:
        print(f"  --> FAIL: L1 should not quote specific failing inputs, but found: {quoted_inputs}")
        overall_ok = False
    # L1 must not name the rule
    if re.search(r"all[- ]?lowercase|lowercase rule|lowercase case", b.body, re.IGNORECASE):
        print(f"  --> FAIL: L1 named the missing rule")
        overall_ok = False
    if "?" not in b.body:
        print(f"  --> FAIL: L1 must end with a question")
        overall_ok = False
    summary.append(("B L1 nudge", b))

    # ---- C. Attempt 2 fail: L2 specific direction ----
    section("C) Attempt 2 fail — expect L2 (category/dimension, still no rule name)")
    c = coach(
        student_display_name="Aarav",
        question=q,
        student_prompt=incomplete_prompt,
        execution=fail_exec,
        assessment=fail_assess,
        attempt_number=2,
        conversation_history=[{"character": "priya", "body": b.body}],
    )
    show("C", c)
    leaks = has_leak(c.body)
    if c.escalation_level != 2:
        print(f"  --> FAIL: level should be 2, got {c.escalation_level}"); overall_ok = False
    if leaks:
        print(f"  --> FAIL: internal terms leaked: {leaks}"); overall_ok = False
    if re.search(r"all[- ]?lowercase|lowercase rule|lowercase case", c.body, re.IGNORECASE):
        print(f"  --> FAIL: L2 named the missing rule"); overall_ok = False
    if "?" not in c.body:
        print(f"  --> FAIL: L2 must end with a question"); overall_ok = False
    summary.append(("C L2 direction", c))

    # ---- D. Attempt 3 fail: L3 direct hint with ONE specific failing input ----
    section("D) Attempt 3 fail — expect L3 (one literal failing input, still no rule name)")
    d = coach(
        student_display_name="Aarav",
        question=q,
        student_prompt=incomplete_prompt,
        execution=fail_exec,
        assessment=fail_assess,
        attempt_number=3,
        conversation_history=[
            {"character": "priya", "body": b.body},
            {"character": "priya", "body": c.body},
        ],
    )
    show("D", d)
    leaks = has_leak(d.body)
    if d.escalation_level != 3:
        print(f"  --> FAIL: level should be 3, got {d.escalation_level}"); overall_ok = False
    if leaks:
        print(f"  --> FAIL: internal terms leaked: {leaks}"); overall_ok = False
    # L3 MUST quote at least one of the failing inputs literally
    quoted_inputs = [inp for inp in failing_inputs if f"'{inp}'" in d.body or f'"{inp}"' in d.body]
    if not quoted_inputs:
        print(f"  --> FAIL: L3 must quote at least one failing input literally")
        overall_ok = False
    else:
        print(f"  --> ok: quoted input(s): {quoted_inputs}")
    if "?" not in d.body:
        print(f"  --> FAIL: L3 must end with a question"); overall_ok = False
    summary.append(("D L3 hint", d))

    # ---- E. Attempt 4 fail: L4 reveal ----
    section("E) Attempt 4 fail — expect L4 (names the missing rule, asks 'why')")
    e = coach(
        student_display_name="Aarav",
        question=q,
        student_prompt=incomplete_prompt,
        execution=fail_exec,
        assessment=fail_assess,
        attempt_number=4,
        conversation_history=[
            {"character": "priya", "body": b.body},
            {"character": "priya", "body": c.body},
            {"character": "priya", "body": d.body},
        ],
    )
    show("E", e)
    if e.escalation_level != 4:
        print(f"  --> FAIL: level should be 4, got {e.escalation_level}"); overall_ok = False
    # L4 MUST mention the all-lowercase concept
    if not re.search(r"all[- ]?lowercase|lowercase\b", e.body, re.IGNORECASE):
        print(f"  --> FAIL: L4 must name the missing rule (all-lowercase)")
        overall_ok = False
    # And ask a 'why' question
    if not re.search(r"\bwhy\b", e.body, re.IGNORECASE):
        print(f"  --> FAIL: L4 should ask a 'why this matters' question")
        overall_ok = False
    # But still no leakage of internal term names
    leaks = has_leak(e.body)
    if leaks:
        print(f"  --> FAIL: internal jargon leaked: {leaks}"); overall_ok = False
    summary.append(("E L4 reveal", e))

    section("SUMMARY")
    for label, r in summary:
        print(f"  {label:20s} -> level={r.escalation_level} expr={r.expression} "
              f"in={r.input_tokens} out={r.output_tokens}")
    print(f"\n  overall_ok = {overall_ok}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
