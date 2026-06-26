"""Scenario E only — verify L4 reveal in isolation."""

from __future__ import annotations

import re
import sys
import textwrap

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from backend.agents.assessor import AssessmentResult
from backend.agents.coach import coach
from backend.core.code_executor import ExecutionResult, TestOutcome
from backend.core.question_loader import load_question


def build_outcomes(tests, failing_inputs):
    out = []
    for t in tests:
        passed = t["input"] not in failing_inputs
        actual = t["expected"] if passed else (not t["expected"])
        out.append(TestOutcome(input=t["input"], expected=t["expected"], actual=actual, passed=passed, error=None))
    return out


def main() -> int:
    q = load_question("p001_detect_capital")
    all_tests = list(q["sample_tests"]) + list(q["hidden_tests"])
    incomplete_prompt = (
        "Write a Python function named detect_capital that takes a word and returns "
        "True if every character is uppercase, or if the first character is uppercase "
        "and the rest are lowercase. Otherwise return False."
    )
    failing_inputs = {"a", "ab", "hello", "leetcode"}
    fail_exec = ExecutionResult(outcomes=build_outcomes(all_tests, failing_inputs))
    fail_assess = AssessmentResult(
        requirement_score=7.5,
        output_score=7.5,
        overall_score=7.5,
        primary_gap="missing_all_lower_case",
        reasoning="Missing the all-lowercase rule.",
        raw_response="", input_tokens=0, output_tokens=0,
    )

    # Minimal history — just one prior message for tone continuity.
    history = [{"character": "priya", "body": "Try this: take the word 'leetcode' and walk it through your rules. What does your function return?"}]

    e = coach(
        student_display_name="Aarav",
        question=q,
        student_prompt=incomplete_prompt,
        execution=fail_exec,
        assessment=fail_assess,
        attempt_number=4,
        conversation_history=history,
        max_tokens=130,
    )

    print("=" * 80)
    print("E) L4 reveal — Aarav, attempt 4")
    print("=" * 80)
    print(f"  expression       : {e.expression}")
    print(f"  escalation_level : {e.escalation_level}")
    print(f"  tokens           : in={e.input_tokens} out={e.output_tokens}")
    print("  body:")
    print(textwrap.indent(e.body, "    "))

    ok = True
    if e.escalation_level != 4:
        print(f"  --> FAIL: level should be 4"); ok = False
    if not re.search(r"all[- ]?lowercase|lowercase\b", e.body, re.IGNORECASE):
        print(f"  --> FAIL: L4 must name the missing rule (all-lowercase)"); ok = False
    if not re.search(r"\bwhy\b", e.body, re.IGNORECASE):
        print(f"  --> FAIL: L4 must ask a 'why' question"); ok = False
    for leak in ("primary_gap", "taxonomy", "reference prompt", "hidden test", "assessor"):
        if leak.lower() in e.body.lower():
            print(f"  --> FAIL: internal term leaked: {leak}"); ok = False

    print()
    print(f"  overall_ok = {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
