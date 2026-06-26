"""
Code Executor (step 2).

Runs untrusted generated code via Python's exec() inside an isolated
subprocess, against a list of test cases, with a wall-clock timeout.

Why subprocess: signal-based alarms aren't portable on Windows, and an
in-process exec() leaks state between attempts. A subprocess gives clean
state, a hard timeout, and isolates crashes from the API server.

Input convention for test cases:
- if `input` is a list, it is splatted as positional args to the function
- otherwise it is passed as a single positional arg

This is not a security sandbox. Generated code is constrained by our Code
Generator (step 3), not by this runner. For multi-tenant deployment, run
the subprocess in a container / seccomp profile / nsjail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# The worker source. Stored as a string so the executor has no extra files
# to ship; piped to `python -` over stdin's *first* line is awkward, so we
# instead pass the worker as `-c` and the payload as stdin JSON.
_WORKER_SOURCE = r"""
import json, sys

def _run():
    raw = sys.stdin.read()
    payload = json.loads(raw)
    code = payload["code"]
    function_name = payload["function_name"]
    tests = payload["tests"]

    namespace = {}
    try:
        exec(compile(code, "<student_code>", "exec"), namespace)
    except SyntaxError as e:
        print(json.dumps({"setup_error": "SyntaxError: " + str(e)}))
        return
    except Exception as e:
        print(json.dumps({"setup_error": type(e).__name__ + ": " + str(e)}))
        return

    fn = namespace.get(function_name)
    if not callable(fn):
        print(json.dumps({
            "setup_error": "function '" + function_name + "' is not defined"
        }))
        return

    results = []
    for case in tests:
        inp = case["input"]
        try:
            if isinstance(inp, list):
                actual = fn(*inp)
            else:
                actual = fn(inp)
            results.append({"actual": actual, "error": None})
        except Exception as e:
            results.append({
                "actual": None,
                "error": type(e).__name__ + ": " + str(e),
            })

    print(json.dumps({"results": results}))

_run()
"""


@dataclass
class TestOutcome:
    input: Any
    expected: Any
    actual: Any
    passed: bool
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    setup_error: Optional[str] = None
    timed_out: bool = False
    outcomes: list[TestOutcome] = field(default_factory=list)
    raw_stderr: str = ""

    @property
    def all_passed(self) -> bool:
        if self.setup_error or self.timed_out:
            return False
        if not self.outcomes:
            return False
        return all(o.passed for o in self.outcomes)

    @property
    def num_passed(self) -> int:
        return sum(1 for o in self.outcomes if o.passed)

    @property
    def num_total(self) -> int:
        return len(self.outcomes)


def execute(
    code: str,
    function_name: str,
    tests: list[dict[str, Any]],
    timeout_seconds: float = 5.0,
    python_executable: Optional[str] = None,
) -> ExecutionResult:
    """Run `code` in a subprocess; call `function_name` against each test.

    Each test must be a dict with keys `input` (any JSON) and `expected` (any JSON).
    Returns an ExecutionResult.
    """
    if not tests:
        return ExecutionResult(setup_error="no tests provided")

    payload = json.dumps({
        "code": code,
        "function_name": function_name,
        "tests": [{"input": t["input"]} for t in tests],
    })

    py = python_executable or sys.executable
    try:
        proc = subprocess.run(
            [py, "-I", "-c", _WORKER_SOURCE],
            input=payload,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        return ExecutionResult(
            timed_out=True,
            raw_stderr=(e.stderr or "") if isinstance(e.stderr, str) else "",
        )

    stdout = (proc.stdout or "").strip()
    stderr = proc.stderr or ""

    if not stdout:
        return ExecutionResult(
            setup_error=f"worker produced no output (returncode={proc.returncode})",
            raw_stderr=stderr,
        )

    # The worker prints exactly one JSON line on its last line. Be defensive.
    last_line = stdout.splitlines()[-1]
    try:
        data = json.loads(last_line)
    except json.JSONDecodeError:
        return ExecutionResult(
            setup_error=f"worker output not JSON: {last_line[:200]!r}",
            raw_stderr=stderr,
        )

    if "setup_error" in data:
        return ExecutionResult(setup_error=str(data["setup_error"]), raw_stderr=stderr)

    raw_results = data.get("results", [])
    outcomes: list[TestOutcome] = []
    for case, r in zip(tests, raw_results):
        expected = case["expected"]
        actual = r.get("actual")
        err = r.get("error")
        passed = err is None and actual == expected
        outcomes.append(
            TestOutcome(
                input=case["input"],
                expected=expected,
                actual=actual,
                passed=passed,
                error=err,
            )
        )

    return ExecutionResult(outcomes=outcomes, raw_stderr=stderr)


__all__ = ["execute", "ExecutionResult", "TestOutcome"]
