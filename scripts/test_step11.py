"""Step 11 verification — Author script.

Two halves:
  OFFLINE (no API):
    A) build_user_message produces a non-empty prompt with the seed embedded.
    B) extract_json strips ```json fences.
    C) validate_question catches missing/bad shape.
    D) verify_reference returns True for the actual p001 reference + tests.
    E) --dry-run prints the prompt + exits 0 with no API call.
    F) --skip-api + --reference-from runs the full validate+verify pipeline
       against an existing enriched file (we feed p001 as the stand-in).

  LIVE (only if ANTHROPIC_API_KEY set + --live):
    G) Attempt an actual author call on the p002 seed; if returned JSON validates
       AND reference_code passes its own tests, count it as a win. Skip silently
       on credit / model errors so CI doesn't break.

Run from project root:
    python -m scripts.test_step11
    python -m scripts.test_step11 --live   # adds the optional live test
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from scripts.author import (  # noqa: E402
    build_user_message,
    extract_json,
    validate_question,
    verify_reference,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
P001_PATH = REPO_ROOT / "questions" / "p001_detect_capital.json"
P002_SEED = REPO_ROOT / "scripts" / "seeds" / "p002_max_consecutive_ones.json"


def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Also run the live author call (uses credits).")
    args = parser.parse_args(argv)

    overall_ok = True

    seed = json.loads(P002_SEED.read_text(encoding="utf-8"))
    p001 = json.loads(P001_PATH.read_text(encoding="utf-8"))

    # ===== A =====
    section("A) build_user_message embeds the seed")
    msg = build_user_message(seed)
    if seed["question_id"] not in msg or "function_signature" not in msg:
        print("  --> FAIL: prompt does not contain seed fields"); overall_ok = False
    if len(msg) < 50:
        print("  --> FAIL: prompt suspiciously short"); overall_ok = False
    print(f"  prompt length: {len(msg)} chars; first line: {msg.splitlines()[0]!r}")

    # ===== B =====
    section("B) extract_json strips ```json fences")
    raw = "Here you go:\n```json\n{\"a\": 1, \"b\": [2, 3]}\n```\nthanks!"
    parsed = extract_json(raw)
    if parsed != {"a": 1, "b": [2, 3]}:
        print(f"  --> FAIL: got {parsed!r}"); overall_ok = False
    raw_plain = '{"a":1}'
    if extract_json(raw_plain) != {"a": 1}:
        print("  --> FAIL: plain JSON not parsed"); overall_ok = False
    raw_with_pre = "prose then {\"a\":2} more prose"
    if extract_json(raw_with_pre) != {"a": 2}:
        print("  --> FAIL: didn't find brace span"); overall_ok = False
    print("  ok: fences stripped, brace-span fallback works")

    # ===== C =====
    section("C) validate_question catches bad shape")
    bad = {"question_id": "x", "title": "y"}  # missing tons
    errs = validate_question(bad)
    print(f"  errors found: {len(errs)} (sample: {errs[0] if errs else None})")
    if len(errs) < 5:
        print("  --> FAIL: should report many missing keys"); overall_ok = False
    # also: bad skill
    bad2 = json.loads(json.dumps(p001))  # deep copy
    bad2["skill_focus"] = ["not_a_real_skill"]
    bad2["gap_taxonomy"][0]["skill"] = "garbage"
    errs2 = validate_question(bad2)
    if not any("skill_focus contains invalid skill" in e for e in errs2):
        print("  --> FAIL: bad skill_focus not caught"); overall_ok = False
    if not any("gap_taxonomy" in e and "garbage" in e for e in errs2):
        print("  --> FAIL: bad gap skill not caught"); overall_ok = False
    # the real p001 must validate clean
    errs3 = validate_question(p001)
    if errs3:
        print(f"  --> FAIL: real p001 produced errors: {errs3}"); overall_ok = False
    print("  ok: validator catches bad shape, accepts real p001")

    # ===== D =====
    section("D) verify_reference passes on real p001")
    ok, summary = verify_reference(p001)
    print(f"  ok={ok}  summary={summary}")
    if not ok:
        print("  --> FAIL: p001 reference should pass all tests"); overall_ok = False

    # And the inverse — sabotaged reference fails verification
    sabotaged = json.loads(json.dumps(p001))
    sabotaged["reference_code"] = "def detect_capital(word):\n    return True\n"
    ok2, summary2 = verify_reference(sabotaged)
    print(f"  sabotaged reference: ok={ok2}  summary={summary2}")
    if ok2:
        print("  --> FAIL: sabotaged reference shouldn't pass"); overall_ok = False

    # ===== E =====
    section("E) --dry-run prints prompt + exits 0, no API call")
    r = subprocess.run(
        [sys.executable, "-m", "scripts.author", "--input", str(P002_SEED), "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "ANTHROPIC_API_KEY": ""},  # prove no API call happens
    )
    print(f"  exit code: {r.returncode}")
    if r.returncode != 0:
        print(f"  stderr: {r.stderr[:300]}"); overall_ok = False
    if "SYSTEM PROMPT" not in r.stdout or "USER MESSAGE" not in r.stdout:
        print("  --> FAIL: dry-run output missing sections"); overall_ok = False
    if "max_consecutive_ones" not in r.stdout:
        print("  --> FAIL: dry-run prompt doesn't mention the seed"); overall_ok = False

    # ===== F =====
    section("F) --skip-api + --reference-from runs full pipeline offline")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        out_path = f.name
    try:
        r = subprocess.run(
            [
                sys.executable, "-m", "scripts.author",
                "--input", str(P002_SEED),
                "--skip-api",
                "--reference-from", str(P001_PATH),
                "--output", out_path,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        print(f"  exit code: {r.returncode}")
        print(f"  stderr (truncated): {r.stderr.strip()[:200]}")
        if r.returncode != 0:
            print("  --> FAIL"); overall_ok = False
        else:
            saved = json.loads(Path(out_path).read_text(encoding="utf-8"))
            if saved.get("question_id") != "p001_detect_capital":
                print("  --> FAIL: file content mismatch"); overall_ok = False
            else:
                print("  ok: full validate+verify pipeline ran, file written")
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass

    # ===== G (optional, live) =====
    if args.live:
        section("G) LIVE author call on p002 seed (costs credits)")
        from backend.config import settings as _settings
        if not _settings.anthropic_api_key:
            print("  skipping — ANTHROPIC_API_KEY not set");
        else:
            from scripts.author import call_author  # imports anthropic lazily
            try:
                q, raw = call_author(seed, max_tokens=2500)
                errs = validate_question(q)
                if errs:
                    print(f"  validator errors: {errs[:3]}")
                    print("  --> NOTE: live call produced invalid shape; not a hard fail")
                else:
                    ok, summary = verify_reference(q)
                    print(f"  reference passes: {ok}  summary={summary}")
                    if not ok:
                        print("  --> NOTE: reference doesn't pass tests; not a hard fail")
                    else:
                        print(f"  enriched JSON keys: {sorted(q.keys())}")
            except Exception as e:
                msg = str(e)[:200]
                print(f"  skipping — live call failed (likely credits): {msg}")
    else:
        section("G) LIVE author call — skipped (pass --live to attempt)")

    section("SUMMARY")
    print(f"  overall_ok = {overall_ok}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
