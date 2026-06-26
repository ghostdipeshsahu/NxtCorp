"""Step 2 sanity check — exercise the Code Executor against P001.

Run from project root:
    python -m scripts.test_step2
"""

from __future__ import annotations

import sys

from backend.core.code_executor import execute
from backend.core.question_loader import (
    function_name_from_signature,
    load_question,
)


def _fmt_outcome(o) -> str:
    status = "PASS" if o.passed else "FAIL"
    err = f"  err={o.error}" if o.error else ""
    return f"  [{status}] input={o.input!r:>16}  expected={o.expected!r:<6}  actual={o.actual!r:<6}{err}"


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    q = load_question("p001_detect_capital")
    fn_name = function_name_from_signature(q)
    all_tests = list(q["sample_tests"]) + list(q["hidden_tests"])

    overall_ok = True

    # ----- 1. Reference code -----
    section("1. Reference code vs all 16 tests (must all PASS)")
    result = execute(q["reference_code"], fn_name, all_tests, timeout_seconds=5)
    if result.setup_error or result.timed_out:
        print(f"  UNEXPECTED FAILURE: setup_error={result.setup_error!r} timed_out={result.timed_out}")
        overall_ok = False
    else:
        for o in result.outcomes:
            print(_fmt_outcome(o))
        print(f"  --> {result.num_passed}/{result.num_total} passed")
        if not result.all_passed:
            overall_ok = False

    # ----- 2. Buggy code: missing all-lowercase branch -----
    section("2. Buggy code (drops all-lowercase rule) — lowercase cases must FAIL")
    buggy = (
        "def detect_capital(word):\n"
        "    if word.isupper():\n"
        "        return True\n"
        "    if word[0].isupper() and word[1:].islower():\n"
        "        return True\n"
        "    return False\n"
    )
    result = execute(buggy, fn_name, all_tests, timeout_seconds=5)
    if result.setup_error or result.timed_out:
        print(f"  UNEXPECTED FAILURE: setup_error={result.setup_error!r} timed_out={result.timed_out}")
        overall_ok = False
    else:
        # With the buggy code (no all-lowercase branch), only lowercase inputs
        # in this question's test set fail — derived from the actual file.
        all_lowercase_inputs = {t["input"] for t in all_tests
                                if isinstance(t["input"], str)
                                and t["input"]
                                and t["input"].islower()}
        expected_failures = all_lowercase_inputs
        actual_failures = {o.input for o in result.outcomes if not o.passed}
        for o in result.outcomes:
            print(_fmt_outcome(o))
        print(f"  expected failures: {sorted(expected_failures)}")
        print(f"  actual   failures: {sorted(actual_failures)}")
        if actual_failures != expected_failures:
            print("  --> MISMATCH: buggy-code failures don't line up with expectation")
            overall_ok = False
        else:
            print("  --> OK (executor distinguishes pass/fail correctly)")

    # ----- 3. Infinite loop must hit timeout -----
    section("3. Infinite loop must trigger timed_out=True")
    spinner = (
        "def detect_capital(word):\n"
        "    while True:\n"
        "        pass\n"
    )
    result = execute(spinner, fn_name, all_tests[:1], timeout_seconds=1.5)
    print(f"  timed_out={result.timed_out}  setup_error={result.setup_error!r}  outcomes={len(result.outcomes)}")
    if not result.timed_out:
        print("  --> FAIL: should have timed out")
        overall_ok = False
    else:
        print("  --> OK")

    # ----- 4. Syntax error must produce setup_error -----
    section("4. Syntax error must populate setup_error")
    broken = "def detect_capital(word\n    return True\n"
    result = execute(broken, fn_name, all_tests[:1], timeout_seconds=5)
    print(f"  setup_error={result.setup_error!r}")
    print(f"  outcomes={len(result.outcomes)}  timed_out={result.timed_out}")
    if not result.setup_error or "SyntaxError" not in result.setup_error:
        print("  --> FAIL: expected SyntaxError in setup_error")
        overall_ok = False
    elif result.outcomes:
        print("  --> FAIL: setup error must produce zero outcomes")
        overall_ok = False
    else:
        print("  --> OK")

    # ----- 5. Wrong function name -----
    section("5. Code defines wrong function name -> setup_error")
    wrong_name = "def something_else(word):\n    return True\n"
    result = execute(wrong_name, fn_name, all_tests[:1], timeout_seconds=5)
    print(f"  setup_error={result.setup_error!r}")
    if not result.setup_error or "not defined" not in result.setup_error:
        print("  --> FAIL: expected 'not defined' setup_error")
        overall_ok = False
    else:
        print("  --> OK")

    section("SUMMARY")
    print(f"  overall_ok = {overall_ok}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
