"""
Author Agent — offline question enrichment (step 11).

Takes a small "seed" JSON describing a task at a high level and expands it
into the full enriched JSON shape the runtime consumes (same shape as
`questions/p001_detect_capital.json`):

    seed (input)                     enriched (output)
    -----------------------------    -----------------------------
    question_id                      question_id
    title                            title, exercise_type, difficulty
    function_signature               function_signature
    problem_sketch                   problem_description (polished)
                                     framing { character, expression, message }
                                     skill_focus
                                     notes
                                     sample_tests (≈ 4)
                                     hidden_tests (10–15, edge-case heavy)
                                     reference_prompt
                                     reference_code
                                     gap_taxonomy (3–5 entries)

The script:
  1. Loads the seed (--input).
  2. Builds the author prompt (or just prints it with --dry-run).
  3. Calls Claude via the Anthropic SDK (honoring ANTHROPIC_BASE_URL so the
     same OpenRouter / direct routing as the rest of the stack works).
  4. Parses the response defensively (strips ```json fences).
  5. Validates the schema shape — required keys, list sizes, etc.
  6. Verifies the produced reference_code passes every sample + hidden test
     by running it through the existing code_executor (no LLM).
  7. Writes to --output (or stdout when no path given).

Use --skip-api to short-circuit step 3 (helpful in CI / when credits are
exhausted) and pass --reference-from to inject a pre-baked enriched file in
place of the LLM response. That makes the validate + verify pipeline
testable end-to-end without burning credits.

Usage examples
--------------
    # Live author call (uses ANTHROPIC_API_KEY + ANTHROPIC_MODEL from .env):
    python -m scripts.author \\
        --input scripts/seeds/p002_max_consecutive_ones.json \\
        --output questions/p002_max_consecutive_ones.json

    # Print the prompt only — no API call, no write:
    python -m scripts.author --input scripts/seeds/p002.json --dry-run

    # Offline test path — use an existing question as a stand-in for the LLM:
    python -m scripts.author --input scripts/seeds/p002.json \\
        --skip-api --reference-from questions/p001_detect_capital.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from backend.config import settings
from backend.core.code_executor import execute
from backend.core.llm import chat as llm_chat, extract_json as _shared_extract_json
from backend.core.question_loader import function_name_from_signature


# A shortened example embedded in the system prompt so the model knows the
# exact shape we want. We use 2 sample + 3 hidden tests here (instead of the
# real-world 4 / 10–15) to keep the system prompt small enough to fit tight
# token budgets — the rules section below tells the model the real counts.
EXAMPLE_QUESTION = {
    "question_id": "p001_detect_capital",
    "exercise_type": 3,
    "title": "Capitalization validator",
    "difficulty": "easy",
    "skill_focus": ["requirement_completeness", "edge_case"],
    "framing": {
        "character": "priya",
        "expression": "happy",
        "message": "Welcome aboard! 🎉 Here's your first ticket. A client's text editor needs a capitalization validator. Take a look — let me know if anything's unclear before you start writing the prompt.",
    },
    "problem_description": "Write a function `detect_capital(word: str) -> bool` that returns True when a word uses capital letters correctly: all uppercase, all lowercase, or only the first letter uppercase.",
    "function_signature": "def detect_capital(word: str) -> bool",
    "notes": "Input is a non-empty string of English letters only.",
    "sample_tests": [
        {"input": "USA", "expected": True, "description": "All uppercase."},
        {"input": "FlaG", "expected": False, "description": "Mixed casing — invalid."},
    ],
    "hidden_tests": [
        {"input": "A", "expected": True, "description": "Single uppercase letter."},
        {"input": "a", "expected": True, "description": "Single lowercase letter."},
        {"input": "HeLLo", "expected": False, "description": "Internal capital — invalid."},
    ],
    "reference_prompt": "Write a Python function named detect_capital that takes a single string parameter `word` and returns a boolean. Return True if the word satisfies any one of these three conditions: 1) every character is uppercase, 2) every character is lowercase, 3) the first character is uppercase AND every character after the first is lowercase. Return False otherwise. Do not validate input.",
    "reference_code": "def detect_capital(word: str) -> bool:\n    if word.isupper():\n        return True\n    if word.islower():\n        return True\n    if word[0].isupper() and word[1:].islower():\n        return True\n    return False",
    "gap_taxonomy": [
        {
            "key": "missing_all_lower_case",
            "description": "Prompt forgets the all-lowercase rule.",
            "skill": "requirement_completeness",
        },
        {
            "key": "internal_caps",
            "description": "Prompt doesn't reject mid-word capitalization.",
            "skill": "edge_case",
        },
    ],
}


SYSTEM_PROMPT = f"""You are the Author Agent for NxtCorp's learning platform. You enrich a tiny task seed into a complete question definition that the runtime can serve.

The student NEVER sees `hidden_tests`, `reference_prompt`, `reference_code`, or `gap_taxonomy`. They are internal. Author them thoroughly.

## Required output shape

You MUST emit JSON matching this schema (no extra keys, no missing keys):

```
{{
  "question_id": <snake_case string — pass through from seed>,
  "exercise_type": <int 1-5 — 3 unless seed says otherwise>,
  "title": <short human title>,
  "difficulty": <"easy" | "medium" | "hard">,
  "skill_focus": <list of 1-2 of: decomposition | edge_case | requirement_completeness | output_verification | iterative_refinement>,
  "framing": {{
    "character": "priya",
    "expression": "happy" | "thinking" | "neutral",
    "message": <Priya's warm in-character ticket framing, 2-3 sentences>
  }},
  "problem_description": <polished, unambiguous English statement of the task — what input, what output, what rules>,
  "function_signature": <exactly `def NAME(arg: TYPE) -> RTYPE` from seed>,
  "notes": <one-line statement of input assumptions (no validation needed, etc.)>,
  "sample_tests": [
    {{ "input": <any JSON>, "expected": <any JSON>, "description": <optional> }},
    ... exactly 4 entries that cover the basic cases the student sees
  ],
  "hidden_tests": [
    {{ "input": ..., "expected": ..., "description": ... }},
    ... 10-15 entries that cover edge cases the student must think about
  ],
  "reference_prompt": <a perfectly precise English specification — long enough to be complete but no longer. A student writing this would produce code that passes every test.>,
  "reference_code": <Python function literally implementing reference_prompt; must pass every test>,
  "gap_taxonomy": [
    {{
      "key": <snake_case identifier for the gap>,
      "description": <one-sentence description of how a student under-specifies this task>,
      "skill": <one of: decomposition | edge_case | requirement_completeness | output_verification | iterative_refinement>
    }},
    ... 3-5 entries
  ]
}}
```

## Critical authoring rules

1. **Hidden tests are the heart of this exercise.** They must include: empty / single-element inputs (if applicable), boundary values, all-of-one-type inputs, alternating / mixed inputs, the largest reasonable input, and at least one input that probes EACH item in `gap_taxonomy`. If a gap exists, a hidden test should expose it.
2. **reference_prompt is the gold standard.** It is what a fully precise student would have written. Be explicit about every rule, every case, every assumption. No ambiguity. No "handles edge cases" hand-waving. If a student wrote your reference_prompt, the code generator would produce passing code.
3. **reference_code must literally implement reference_prompt** — no extra cleverness, no missing branches.
4. **gap_taxonomy** drives the Coach Agent. Each entry is a real mistake students make (e.g. forgetting all-lowercase). The runtime maps the student's failing tests to one of these keys; pick gaps that the hidden tests can actually expose.
5. **input values in tests use only JSON-native types** (string, int, float, bool, null, list, object). No tuples — use lists.
6. **JSON only, no markdown fences, no commentary.** Start with `{{` and end with `}}`.

## Example (showing shape — your real output has 4 sample + 10-15 hidden tests)

```json
{json.dumps(EXAMPLE_QUESTION, indent=2)}
```
"""


def build_user_message(seed: dict) -> str:
    parts = [
        "Enrich this seed into the full question JSON. Pass `question_id` and `function_signature` through verbatim.",
        "",
        "SEED:",
        json.dumps(seed, indent=2),
        "",
        "Emit JSON only. No markdown fences.",
    ]
    return "\n".join(parts)


# Local alias so the existing test imports (`from scripts.author import extract_json`)
# keep working.
extract_json = _shared_extract_json


REQUIRED_KEYS = (
    "question_id",
    "exercise_type",
    "title",
    "difficulty",
    "skill_focus",
    "framing",
    "problem_description",
    "function_signature",
    "notes",
    "sample_tests",
    "hidden_tests",
    "reference_prompt",
    "reference_code",
    "gap_taxonomy",
)

VALID_SKILLS = {
    "decomposition",
    "edge_case",
    "requirement_completeness",
    "output_verification",
    "iterative_refinement",
}


def validate_question(q: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for k in REQUIRED_KEYS:
        if k not in q:
            errors.append(f"missing required key: {k}")

    if "framing" in q:
        framing = q["framing"]
        if not isinstance(framing, dict):
            errors.append("framing must be an object")
        else:
            for fk in ("character", "expression", "message"):
                if fk not in framing:
                    errors.append(f"framing.{fk} missing")

    for list_key, min_n, max_n in (
        ("sample_tests", 2, 8),
        ("hidden_tests", 3, 30),
        ("gap_taxonomy", 2, 8),
        ("skill_focus", 1, 3),
    ):
        if list_key in q:
            v = q[list_key]
            if not isinstance(v, list):
                errors.append(f"{list_key} must be a list")
            elif not (min_n <= len(v) <= max_n):
                errors.append(f"{list_key} has {len(v)} entries (expected {min_n}–{max_n})")

    for test_field in ("sample_tests", "hidden_tests"):
        for i, t in enumerate(q.get(test_field, []) or []):
            if not isinstance(t, dict):
                errors.append(f"{test_field}[{i}] must be an object")
                continue
            if "input" not in t or "expected" not in t:
                errors.append(f"{test_field}[{i}] missing input or expected")

    for i, g in enumerate(q.get("gap_taxonomy", []) or []):
        if not isinstance(g, dict):
            errors.append(f"gap_taxonomy[{i}] must be an object")
            continue
        for gk in ("key", "description", "skill"):
            if gk not in g:
                errors.append(f"gap_taxonomy[{i}].{gk} missing")
        if g.get("skill") and g["skill"] not in VALID_SKILLS:
            errors.append(f"gap_taxonomy[{i}].skill {g['skill']!r} not in {sorted(VALID_SKILLS)}")

    for s in q.get("skill_focus", []) or []:
        if s not in VALID_SKILLS:
            errors.append(f"skill_focus contains invalid skill: {s!r}")

    if isinstance(q.get("question_id"), str):
        if not q["question_id"].replace("_", "").isalnum():
            errors.append("question_id must be snake_case ascii")

    return errors


def verify_reference(q: dict[str, Any]) -> tuple[bool, str]:
    """Run reference_code through the code_executor against all tests.

    Returns (ok, summary). ok is True only if every test passes.
    """
    fn_name = function_name_from_signature(q)
    all_tests = list(q.get("sample_tests") or []) + list(q.get("hidden_tests") or [])
    if not all_tests:
        return (False, "no tests to verify against")
    res = execute(q["reference_code"], fn_name, all_tests, timeout_seconds=8)
    if res.setup_error:
        return (False, f"setup_error: {res.setup_error}")
    if res.timed_out:
        return (False, "reference_code timed out")
    if not res.all_passed:
        failed_inputs = [o.input for o in res.outcomes if not o.passed]
        return (False, f"{res.num_passed}/{res.num_total} passed; failed inputs: {failed_inputs!r}")
    return (True, f"{res.num_passed}/{res.num_total}")


def call_author(seed: dict, *, max_tokens: int, model: Optional[str] = None) -> tuple[dict, str]:
    """Hit the configured LLM (via llm.chat shim) to enrich the seed.

    Returns (parsed_question, raw_response).
    """
    result = llm_chat(
        system=SYSTEM_PROMPT,
        user=build_user_message(seed),
        max_tokens=max_tokens,
        model=model,
        temperature=0.2,
        response_format_json=True,
    )
    return extract_json(result.text), result.text


# ----- CLI -----

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enrich a seed into a full question JSON.")
    p.add_argument("--input", required=True, help="Path to seed JSON.")
    p.add_argument("--output", default=None, help="Path to write enriched JSON. Default: stdout.")
    p.add_argument("--model", default=None, help="Override ANTHROPIC_MODEL.")
    p.add_argument("--max-tokens", type=int, default=4000, help="Cap on generated tokens.")
    p.add_argument("--dry-run", action="store_true", help="Print the author prompt and exit.")
    p.add_argument("--skip-api", action="store_true", help="Skip the API call; use --reference-from.")
    p.add_argument(
        "--reference-from",
        default=None,
        help="With --skip-api, treat this enriched JSON file as the LLM response (for offline testing).",
    )
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip running reference_code through the executor.",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    seed_path = Path(args.input)
    if not seed_path.is_file():
        print(f"error: seed not found: {seed_path}", file=sys.stderr)
        return 2
    seed = json.loads(seed_path.read_text(encoding="utf-8"))

    if args.dry_run:
        print("=== SYSTEM PROMPT ===")
        print(SYSTEM_PROMPT)
        print()
        print("=== USER MESSAGE ===")
        print(build_user_message(seed))
        return 0

    if args.skip_api:
        if not args.reference_from:
            print("error: --skip-api requires --reference-from", file=sys.stderr)
            return 2
        q = json.loads(Path(args.reference_from).read_text(encoding="utf-8"))
        raw = "(--skip-api: response loaded from " + args.reference_from + ")"
    else:
        if not settings.anthropic_api_key:
            print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
            return 2
        q, raw = call_author(seed, max_tokens=args.max_tokens, model=args.model)

    errors = validate_question(q)
    if errors:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if not args.no_verify:
        ok, summary = verify_reference(q)
        print(f"reference_code verification: {summary}", file=sys.stderr)
        if not ok:
            print("ERROR: reference_code does not pass its own tests.", file=sys.stderr)
            return 1

    serialized = json.dumps(q, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
