"""Step 6 integration test — walk the full pipeline through the API.

Uses a temp SQLite DB so it leaves no permanent state. Runs ONE attempt
(the reference prompt) so the budget hit is bounded — 3 live LLM calls
total (code_generator + assessor + coach).

Run from project root:
    python -m scripts.test_step6
"""

from __future__ import annotations

import os
import sys
import tempfile

# Point DB at a throwaway file BEFORE importing the app (engine binds at import).
_fd, _DB_PATH = tempfile.mkstemp(prefix="nxtcorp_step6_", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

import textwrap  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


def section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def main() -> int:
    overall_ok = True

    with TestClient(app) as client:
        # ----- Register -----
        section("1) Register a new player")
        r = client.post(
            "/api/auth/register",
            json={
                "username": "aarav_step6",
                "password": "hunter2hunter2",
                "display_name": "Aarav",
                "avatar_id": "avatar_02",
            },
        )
        print(f"  status: {r.status_code}")
        if r.status_code != 201:
            print(f"  body: {r.text}"); return 1
        token = r.json()["access_token"]
        print(f"  token prefix: {token[:24]}...")

        auth = {"Authorization": f"Bearer {token}"}

        # ----- Profile sanity check -----
        section("2) GET /api/player/profile — sanity check skill rows exist")
        r = client.get("/api/player/profile", headers=auth)
        print(f"  status: {r.status_code}")
        prof = r.json()
        print(f"  job_title: {prof['job_title']}  xp: {prof['total_xp']}  skills: {len(prof['skills'])}")
        if r.status_code != 200 or prof["job_title"] != "AI Trainee":
            print("  --> FAIL"); overall_ok = False
        if len(prof["skills"]) != 5:
            print(f"  --> FAIL: expected 5 skill rows, got {len(prof['skills'])}"); overall_ok = False

        # ----- GET current task -----
        section("3) GET /api/task/current — sample tests visible, hidden tests must NOT leak")
        r = client.get("/api/task/current", headers=auth)
        print(f"  status: {r.status_code}")
        task = r.json()
        print(f"  question_id: {task['question_id']}")
        print(f"  title: {task['title']}")
        print(f"  framing_character: {task['framing_character']}")
        print(f"  sample_tests: {len(task['sample_tests'])}")
        if task["question_id"] != "p001_detect_capital":
            print("  --> FAIL: wrong question id"); overall_ok = False
        if len(task["sample_tests"]) != 4:
            print("  --> FAIL: expected 4 sample tests"); overall_ok = False
        # Critical: response must NEVER expose hidden_tests / reference_prompt / reference_code
        for forbidden in ("hidden_tests", "reference_prompt", "reference_code", "gap_taxonomy"):
            if forbidden in r.text:
                print(f"  --> FAIL: response leaks {forbidden!r}"); overall_ok = False

        # ----- POST /api/task/run with reference prompt -----
        section("4) POST /api/task/run — full pipeline on the reference prompt")
        reference_prompt = (
            "Write a Python function named detect_capital that takes a single string "
            "parameter `word` (a non-empty string of English letters only) and returns "
            "a boolean. Return True if the word satisfies any one of these three "
            "conditions: 1) every character in the word is uppercase, 2) every "
            "character in the word is lowercase, 3) the first character is uppercase "
            "AND every character after the first is lowercase. Return False otherwise. "
            "Do not handle empty strings, digits, spaces, or non-letter characters."
        )
        r = client.post(
            "/api/task/run",
            headers=auth,
            json={"student_prompt": reference_prompt, "attempt_number": 1},
        )
        print(f"  status: {r.status_code}")
        if r.status_code != 200:
            print(f"  body: {r.text[:500]}"); return 1
        run = r.json()
        print(f"  attempt_id      : {run['attempt_id']}")
        print(f"  all_passed      : {run['all_passed']}")
        print(f"  sample_passed   : {run['sample_passed']}/{run['sample_total']}")
        print(f"  hidden_passed   : {run['hidden_passed']}/{run['hidden_total']}")
        print(f"  xp_earned       : {run['xp_earned']}")
        print(f"  badges_earned   : {run['badges_earned']}")
        print(f"  primary_gap     : {run['primary_gap']!r}")
        print(f"  skill_updates   : {run['skill_updates']}")
        cm = run["coach_message"]
        print(f"  coach: char={cm['character']}  expr={cm['expression']}  level={cm['escalation_level']}")
        print("  coach body:")
        print(textwrap.indent(cm["body"], "    "))

        # Assertions for the reference-prompt success case
        if not run["all_passed"]:
            print("  --> FAIL: reference prompt should pass all tests"); overall_ok = False
        if run["sample_total"] <= 0 or run["hidden_total"] <= 0:
            print("  --> FAIL: expected at least 1 sample + 1 hidden"); overall_ok = False
        if run["xp_earned"] != 200:  # 150 + 50 first-try bonus
            print(f"  --> FAIL: expected xp_earned=200 (first-try bonus), got {run['xp_earned']}"); overall_ok = False
        if "first_try" not in run["badges_earned"]:
            print("  --> FAIL: first_try badge missing"); overall_ok = False
        if cm["character"] != "priya" or cm["escalation_level"] != 0:
            print("  --> FAIL: coach should be Priya at level 0 (celebration)"); overall_ok = False
        if run["primary_gap"] is not None:
            print(f"  --> FAIL: primary_gap should be None on full pass, got {run['primary_gap']!r}"); overall_ok = False
        # Spec critical rule #1: students NEVER see generated code
        if "generated_code" in r.text:
            print("  --> FAIL: response leaks generated_code"); overall_ok = False
        # Spec critical rule #2: students NEVER see hidden tests — derive
        # forbidden inputs from the actual question on disk (catalog-driven).
        from backend.core.question_loader import load_question
        question_for_assert = load_question(task["question_id"])
        sample_inputs = {repr(t["input"]) for t in question_for_assert.get("sample_tests") or []}
        hidden_only = []
        for t in question_for_assert.get("hidden_tests") or []:
            r_inp = repr(t["input"])
            if r_inp not in sample_inputs:
                hidden_only.append(t["input"])
        for inp in hidden_only:
            # JSON encoding strips outer quotes for strings; check both forms.
            haystack = r.text
            needle_repr = repr(inp)
            if needle_repr in haystack:
                print(f"  --> FAIL: response leaks hidden-only test input {needle_repr}"); overall_ok = False

        # ----- Profile reflects the XP bump and skill_focus bumps -----
        section("5) GET /api/player/profile — XP and skill_focus skills bumped")
        r = client.get("/api/player/profile", headers=auth)
        prof = r.json()
        print(f"  total_xp: {prof['total_xp']}")
        skills_by_key = {s["skill"]: s["score"] for s in prof["skills"]}
        print(f"  skills  : {skills_by_key}")
        if prof["total_xp"] != 200:
            print(f"  --> FAIL: expected total_xp=200, got {prof['total_xp']}"); overall_ok = False
        # Catalog-driven: every skill in this question's skill_focus must be > 0.
        for skill in question_for_assert.get("skill_focus") or []:
            if skills_by_key.get(skill, 0) <= 0:
                print(f"  --> FAIL: {skill} should be > 0 after pass"); overall_ok = False

        section("SUMMARY")
        print(f"  overall_ok = {overall_ok}")

    # Best-effort cleanup of the temp DB file.
    try:
        os.remove(_DB_PATH)
    except OSError:
        pass

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
