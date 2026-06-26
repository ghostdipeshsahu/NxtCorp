"""
Rebalance the 15-question catalog so 3 questions land in each exercise type.

Assignment (chosen to fit each type's mechanic):

  Type 1 — Decompose:        p004 grade, p011 fizzbuzz, p015 bmi_category
  Type 2 — Spot the Gap:     p001 detect_capital, p005 second_largest, p010 remove_duplicates
  Type 3 — Specify+Execute:  p002 is_palindrome, p008 is_prime, p014 power
  Type 4 — Verify:           p003 digit_sum, p006 count_vowels, p013 is_anagram
  Type 5 — Diagnose+Fix:     p007 flatten, p009 reverse_words, p012 rotate_list

For each non-Type-3 conversion we add the fields its runtime + UI expect:

  Type 1:  expected_subtasks   = positive rephrase of gap_taxonomy entries
  Type 2:  flawed_prompt       = reference_prompt with 1-2 rules removed
           expected_gaps       = subset of gap_taxonomy that match removed rules
  Type 4:  target_code         = reference_code (correct) — student writes tests
                                   that should pass and cover the gap_taxonomy
  Type 5:  failing_prompt      = a deliberately incomplete prompt (the kind a
                                   student might write); the runtime will use
                                   it as the conversation history's "previous
                                   attempt" so the player can write a fix
           failing_inputs_hint = inputs from sample_tests that the failing
                                   prompt would mis-handle

Existing fields (problem_description, sample_tests, hidden_tests,
reference_code, gap_taxonomy, etc.) are preserved so the per-type pipelines
have what they need.

Run from project root:
    python -m scripts.rebalance_types          # writes
    python -m scripts.rebalance_types --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = REPO_ROOT / "questions"


# (filename without extension) -> exercise_type
ASSIGNMENT = {
    # Type 1 — Decompose
    "p004_grade": 1,
    "p011_fizzbuzz": 1,
    "p015_bmi_category": 1,
    # Type 2 — Spot the Gap
    "p001_detect_capital": 2,
    "p005_second_largest": 2,
    "p010_remove_duplicates": 2,
    # Type 3 — Specify and Execute
    "p002_is_palindrome": 3,
    "p008_is_prime": 3,
    "p014_power": 3,
    # Type 4 — Verify
    "p003_digit_sum": 4,
    "p006_count_vowels": 4,
    "p013_is_anagram": 4,
    # Type 5 — Diagnose and Fix
    "p007_flatten": 5,
    "p009_reverse_words": 5,
    "p012_rotate_list": 5,
}


# ---------- Per-type generators ----------

def make_subtasks(q: dict[str, Any]) -> list[dict[str, str]]:
    """Type 1: turn gap_taxonomy descriptions into positive sub-task lines."""
    out = []
    seen_keys = set()
    for g in q.get("gap_taxonomy") or []:
        desc = g.get("description", "")
        # description in our normalized form is "Prompt under-specifies: <real>".
        # Strip that leader to get a positive sentence the student should write.
        body = re.sub(r"^\s*Prompt under-specifies:\s*", "", desc, flags=re.IGNORECASE)
        body = body.strip()
        if not body:
            continue
        key = g["key"].replace("missing_", "subtask_")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append({"key": key, "description": body})
    if not out:
        # safety net — minimum 2 sub-tasks so scoring has something
        out = [
            {"key": "subtask_function_contract", "description": "Specify the function signature and the type of value it returns."},
            {"key": "subtask_main_rule", "description": "State the main rule that maps input to output."},
        ]
    return out


def derive_flawed_prompt(q: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """Type 2: keep the reference_prompt but strip up to 2 sentences that
    correspond to specific gap_taxonomy entries. Return (flawed_prompt,
    list-of-gap-entries-that-are-now-missing).
    """
    reference = q.get("reference_prompt", "") or ""
    # Sentence-split (simple, good enough for our short prompts).
    sentences = re.split(r"(?<=[.!?])\s+", reference.strip())

    gap_keys: list[dict[str, str]] = []
    keep: list[str] = []
    dropped_sentences: list[str] = []
    drop_budget = 2

    for s in sentences:
        s_stripped = s.strip()
        if not s_stripped:
            continue
        # If this sentence mentions a concept that matches a gap_taxonomy
        # description, drop it (up to drop_budget times).
        matched_gap = None
        for g in q.get("gap_taxonomy") or []:
            desc = g.get("description", "").lower()
            # crude keyword overlap — pick a few distinctive nouns
            keywords = [w for w in re.findall(r"[a-z]{4,}", desc)][:6]
            if keywords and any(k in s_stripped.lower() for k in keywords):
                matched_gap = g
                break
        if matched_gap and drop_budget > 0:
            dropped_sentences.append(s_stripped)
            gap_keys.append({
                "key": matched_gap["key"],
                "description": matched_gap.get("description", ""),
            })
            drop_budget -= 1
            continue
        keep.append(s_stripped)

    # If nothing dropped (no keyword match), strip the last sentence as
    # a fallback so the prompt still has a visible gap.
    if not dropped_sentences and sentences:
        keep = sentences[:-1]
        dropped_sentences = [sentences[-1].strip()]
        # Use the first taxonomy entry as the expected gap.
        gt = (q.get("gap_taxonomy") or [None])[0]
        if gt:
            gap_keys = [{"key": gt["key"], "description": gt.get("description", "")}]

    flawed = " ".join(keep).strip()
    # If we somehow stripped everything, fall back to the original.
    if not flawed:
        flawed = reference
    return flawed, gap_keys[:3]


def derive_failing_prompt(q: dict[str, Any]) -> tuple[str, list[Any]]:
    """Type 5: produce a deliberately incomplete prompt + which sample test
    inputs that prompt would mis-handle (for the UI hint).
    """
    reference = q.get("reference_prompt", "") or ""
    sentences = re.split(r"(?<=[.!?])\s+", reference.strip())
    # Drop the LAST sentence as a stand-in for "the student forgot a rule".
    failing = " ".join(sentences[:-1]).strip() if len(sentences) > 1 else reference

    # Hint: which sample inputs would the failing prompt likely break on?
    # Pick all samples for which `expected` is "interesting" (False/0/empty) —
    # those are usually the edge cases the missing rule was supposed to handle.
    hints = []
    for t in q.get("sample_tests") or []:
        exp = t.get("expected")
        if exp in (False, 0, "", None) or (isinstance(exp, list) and len(exp) == 0):
            hints.append(t["input"])
    if not hints and q.get("sample_tests"):
        # Default: the last sample test.
        hints = [q["sample_tests"][-1]["input"]]
    return failing, hints[:3]


# ---------- Main rewrite ----------

def convert_one(path: Path) -> dict[str, Any] | None:
    q = json.loads(path.read_text(encoding="utf-8"))
    slug = path.stem
    new_type = ASSIGNMENT.get(slug)
    if new_type is None:
        print(f"  {path.name}: NOT IN ASSIGNMENT — leaving as-is")
        return None

    old_type = q.get("exercise_type")
    q["exercise_type"] = new_type

    # Strip any prior type-specific fields so re-runs are clean.
    for k in ("expected_subtasks", "flawed_prompt", "expected_gaps",
              "target_code", "failing_prompt", "failing_inputs_hint"):
        q.pop(k, None)

    if new_type == 1:
        q["expected_subtasks"] = make_subtasks(q)
    elif new_type == 2:
        flawed, gaps = derive_flawed_prompt(q)
        q["flawed_prompt"] = flawed
        q["expected_gaps"] = gaps or [
            {"key": "general_gap", "description": "Prompt is missing at least one rule from the spec."}
        ]
    elif new_type == 3:
        pass  # nothing extra
    elif new_type == 4:
        # Student writes test cases for this code. We hand them the reference
        # (correct) implementation; their job is to write tests that would
        # catch a buggy variant. The runtime scores against gap_taxonomy.
        q["target_code"] = q.get("reference_code", "")
    elif new_type == 5:
        failing, hints = derive_failing_prompt(q)
        q["failing_prompt"] = failing
        q["failing_inputs_hint"] = hints

    print(f"  {path.name}: type {old_type} -> {new_type}")
    return q


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    paths = sorted(QUESTIONS_DIR.glob("p*.json"))
    if not paths:
        print(f"no questions in {QUESTIONS_DIR}", file=sys.stderr)
        return 2

    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for path in paths:
        new_q = convert_one(path)
        if new_q is None:
            continue
        counts[new_q["exercise_type"]] += 1
        if not args.dry_run:
            path.write_text(
                json.dumps(new_q, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    print()
    print("final distribution:")
    for t, n in sorted(counts.items()):
        print(f"  type {t}: {n}")
    return 0 if all(n == 3 for n in counts.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
