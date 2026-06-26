"""Step 4 verification — exercise the Assessor on three P001 scenarios.

Canned ExecutionResult objects so we don't burn credits regenerating code
through step 3. The execution outcomes used here are the actual outcomes
we observed in step 3.

Run from project root:
    python -m scripts.test_step4
"""

from __future__ import annotations

import sys
import textwrap
from typing import Any

from backend.agents.assessor import assess
from backend.core.code_executor import ExecutionResult, TestOutcome
from backend.core.question_loader import load_question


def build_outcomes(tests: list[dict[str, Any]], failing_inputs: set[Any]) -> list[TestOutcome]:
    outcomes: list[TestOutcome] = []
    for t in tests:
        inp = t["input"]
        expected = t["expected"]
        passed = inp not in failing_inputs
        # synthesize a believable "actual" for failing cases
        actual = expected if passed else (not expected)
        outcomes.append(
            TestOutcome(
                input=inp,
                expected=expected,
                actual=actual,
                passed=passed,
                error=None,
            )
        )
    return outcomes


def section(title: str) -> None:
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


def show_assessment(label: str, prompt: str, result) -> None:
    print(f"\n[{label}]")
    print("PROMPT:")
    print(textwrap.indent(prompt.strip(), "    "))
    print()
    print(f"  requirement_score: {result.requirement_score}")
    print(f"  output_score     : {result.output_score}")
    print(f"  overall_score    : {result.overall_score}")
    print(f"  primary_gap      : {result.primary_gap!r}")
    print(f"  reasoning        : {result.reasoning}")
    print(f"  tokens           : in={result.input_tokens} out={result.output_tokens}")


def main() -> int:
    q = load_question("p001_detect_capital")
    all_tests = list(q["sample_tests"]) + list(q["hidden_tests"])
    valid_gap_keys = {g["key"] for g in q["gap_taxonomy"]}

    overall_ok = True

    # ===== Case 1: Reference prompt — 16/16 pass =====
    section("Case 1: Reference prompt (16/16 pass) — expect HIGH req, primary_gap=None")
    ref_outcomes = build_outcomes(all_tests, failing_inputs=set())
    ref_exec = ExecutionResult(outcomes=ref_outcomes)
    ref_result = assess(q["reference_prompt"], q, ref_exec)
    show_assessment("REFERENCE", q["reference_prompt"], ref_result)

    if ref_result.requirement_score < 7.0:
        print("  --> FAIL: reference prompt should score >= 7 on requirement_score")
        overall_ok = False
    if ref_result.output_score != 10.0:
        print("  --> FAIL: output_score should be 10.0 when 16/16 pass")
        overall_ok = False
    if ref_result.primary_gap is not None:
        print("  --> FAIL: primary_gap should be None when all tests pass")
        overall_ok = False

    # ===== Case 2: Vague prompt — `return True`, 11/16 =====
    section("Case 2: Vague prompt (11/16, mixed failures) — expect LOW req, some gap key")
    vague_prompt = (
        "Write a function called detect_capital that takes a word and "
        "checks if it's capitalized correctly. Return True if yes, False if no."
    )
    vague_failures = {"ABc", "AbC", "FlaG", "HeLLo", "aB"}
    vague_outcomes = build_outcomes(all_tests, failing_inputs=vague_failures)
    vague_exec = ExecutionResult(outcomes=vague_outcomes)
    vague_result = assess(vague_prompt, q, vague_exec)
    show_assessment("VAGUE", vague_prompt, vague_result)

    if vague_result.requirement_score > 5.0:
        print(f"  --> FAIL: vague prompt should score <= 5, got {vague_result.requirement_score}")
        overall_ok = False
    expected_output_score = round(10.0 * 11 / 16, 2)
    if vague_result.output_score != expected_output_score:
        print(f"  --> FAIL: output_score should be {expected_output_score}")
        overall_ok = False
    # primary_gap may be None or any valid key — vague prompts could match any gap
    if vague_result.primary_gap is not None and vague_result.primary_gap not in valid_gap_keys:
        print(f"  --> FAIL: primary_gap {vague_result.primary_gap!r} not in taxonomy")
        overall_ok = False

    # ===== Case 3: Incomplete prompt (missing all-lowercase rule) — 12/16 =====
    section("Case 3: Incomplete prompt (12/16, lowercase fails) — expect primary_gap=missing_all_lower_case")
    incomplete_prompt = (
        "Write a Python function named detect_capital that takes a single "
        "string parameter `word` (non-empty, letters only) and returns a "
        "boolean. Return True if either of these holds: (a) every character "
        "is uppercase, or (b) the first character is uppercase and every "
        "character after the first is lowercase. Otherwise return False. "
        "Do not validate the input."
    )
    incomplete_failures = {"a", "ab", "hello", "leetcode"}
    incomplete_outcomes = build_outcomes(all_tests, failing_inputs=incomplete_failures)
    incomplete_exec = ExecutionResult(outcomes=incomplete_outcomes)
    incomplete_result = assess(incomplete_prompt, q, incomplete_exec)
    show_assessment("INCOMPLETE", incomplete_prompt, incomplete_result)

    expected_output_score_3 = round(10.0 * 12 / 16, 2)
    if incomplete_result.output_score != expected_output_score_3:
        print(f"  --> FAIL: output_score should be {expected_output_score_3}")
        overall_ok = False
    if incomplete_result.primary_gap != "missing_all_lower_case":
        print(
            f"  --> FAIL: expected primary_gap='missing_all_lower_case', "
            f"got {incomplete_result.primary_gap!r}"
        )
        overall_ok = False
    # This prompt is precise except for the one missing branch — score should
    # be in the middle, not near zero.
    if not (5.0 <= incomplete_result.requirement_score <= 9.0):
        print(
            f"  --> FAIL: incomplete-but-otherwise-precise prompt should score 5-9, "
            f"got {incomplete_result.requirement_score}"
        )
        overall_ok = False

    section("SUMMARY")
    print(f"  case 1 (reference) : req={ref_result.requirement_score}  out={ref_result.output_score}  "
          f"gap={ref_result.primary_gap!r}")
    print(f"  case 2 (vague)     : req={vague_result.requirement_score}  out={vague_result.output_score}  "
          f"gap={vague_result.primary_gap!r}")
    print(f"  case 3 (incomplete): req={incomplete_result.requirement_score}  out={incomplete_result.output_score}  "
          f"gap={incomplete_result.primary_gap!r}")
    print(f"  overall_ok = {overall_ok}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
