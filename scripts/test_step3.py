"""Step 3 sanity check — drive the Code Generator with three prompt qualities,
prove that literalism actually works (vague fails, precise passes).

Run from project root with ANTHROPIC_API_KEY set:
    python -m scripts.test_step3
"""

from __future__ import annotations

import sys
import textwrap

from backend.core.code_executor import execute
from backend.core.code_generator import generate_code
from backend.core.question_loader import (
    function_name_from_signature,
    load_question,
)


def section(title: str) -> None:
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


def show_code(code: str, max_chars: int = 800) -> None:
    snippet = code if len(code) <= max_chars else code[:max_chars] + "\n... [truncated]"
    print(textwrap.indent(snippet, "    "))


def run_case(label: str, prompt: str, question, all_tests, fn_name) -> tuple[int, int, set[str]]:
    section(label)
    print("PROMPT:")
    print(textwrap.indent(prompt.strip(), "    "))

    result = generate_code(prompt, question)
    print()
    print(
        f"USAGE: input={result.input_tokens}  output={result.output_tokens}  "
        f"cache_read={result.cache_read_input_tokens}  cache_write={result.cache_creation_input_tokens}"
    )
    print()
    print("GENERATED CODE:")
    show_code(result.code)

    exec_result = execute(result.code, fn_name, all_tests, timeout_seconds=5)
    if exec_result.setup_error or exec_result.timed_out:
        print()
        print(f"  SETUP/TIMEOUT FAILURE: setup_error={exec_result.setup_error!r} "
              f"timed_out={exec_result.timed_out}")
        return (0, len(all_tests), set())

    failures = {str(o.input) for o in exec_result.outcomes if not o.passed}
    print()
    print(f"  --> {exec_result.num_passed}/{exec_result.num_total} passed")
    if failures:
        print(f"  --> failures on: {sorted(failures)}")
    return (exec_result.num_passed, exec_result.num_total, failures)


def main() -> int:
    q = load_question("p001_detect_capital")
    fn_name = function_name_from_signature(q)
    all_tests = list(q["sample_tests"]) + list(q["hidden_tests"])

    overall_ok = True

    # ---- 1. Reference prompt — precise, complete ----
    ref_passed, ref_total, ref_failures = run_case(
        "1. Reference prompt (precise, complete) — should be 16/16",
        q["reference_prompt"],
        q,
        all_tests,
        fn_name,
    )
    if ref_passed != ref_total:
        print("  --> EXPECTED FULL PASS — FAIL")
        overall_ok = False

    # ---- 2. Vague prompt — student forgot all the rules ----
    vague_prompt = (
        "Write a function called detect_capital that takes a word and "
        "checks if it's capitalized correctly. Return True if yes, False if no."
    )
    vague_passed, vague_total, vague_failures = run_case(
        "2. Vague prompt — should fail on at least a few hidden cases",
        vague_prompt,
        q,
        all_tests,
        fn_name,
    )
    if vague_passed == vague_total:
        print()
        print("  --> EXPECTED SOME FAILURES (literal generator should not")
        print("      'helpfully' infer the three correct cases). FAIL.")
        overall_ok = False

    # ---- 3. Precise but missing the all-lowercase rule ----
    incomplete_prompt = (
        "Write a Python function named detect_capital that takes a single "
        "string parameter `word` (non-empty, letters only) and returns a "
        "boolean. Return True if either of these holds: (a) every character "
        "is uppercase, or (b) the first character is uppercase and every "
        "character after the first is lowercase. Otherwise return False. "
        "Do not validate the input."
    )
    inc_passed, inc_total, inc_failures = run_case(
        "3. Precise but missing all-lowercase rule — should fail exactly on lowercase words",
        incomplete_prompt,
        q,
        all_tests,
        fn_name,
    )
    expected_failures = {"leetcode", "a", "ab", "hello"}
    if inc_failures != expected_failures:
        print()
        print(f"  expected failures: {sorted(expected_failures)}")
        print(f"  actual failures:   {sorted(inc_failures)}")
        print("  --> FAIL: literal generator should produce code that fails "
              "exactly on the all-lowercase inputs the prompt omitted.")
        overall_ok = False

    section("SUMMARY")
    print(f"  case 1 (reference)          : {ref_passed}/{ref_total}")
    print(f"  case 2 (vague)              : {vague_passed}/{vague_total}  failures={sorted(vague_failures)}")
    print(f"  case 3 (missing one branch) : {inc_passed}/{inc_total}  failures={sorted(inc_failures)}")
    print(f"  overall_ok = {overall_ok}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
