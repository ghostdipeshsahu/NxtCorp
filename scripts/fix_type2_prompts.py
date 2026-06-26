"""
Hand-crafted Type 2 (Spot the Gap) prompts — one shot.

The previous rebalance_types.derive_flawed_prompt() chopped sentences at
arbitrary keyword matches, often leaving prompts that start mid-sentence
(e.g. "HELLO), (2)…"). This script overwrites the three Type 2 questions
with deliberately authored flawed prompts + matching expected_gaps so each
one reads like something a junior dev (Arjun) actually wrote.

Each flawed prompt:
  - Reads as a complete English instruction (no orphan tokens)
  - Has clear-but-fixable gaps the student can spot
  - Aligns with the question's reference behavior

Run from project root:
    python -m scripts.fix_type2_prompts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
Q_DIR = REPO_ROOT / "questions"


OVERRIDES = {
    "p001_detect_capital": {
        "flawed_prompt": (
            "Write a function detect_capital(word) that checks if a word is "
            "capitalized correctly. It should return True when the word is in "
            "all caps (like HELLO) or when only the first letter is capital "
            "(like Hello). Otherwise return False."
        ),
        "expected_gaps": [
            {
                "key": "missing_all_lowercase_rule",
                "description": "The prompt forgets that all-lowercase words (e.g. 'hello') should also return True.",
            },
            {
                "key": "missing_return_type_constraint",
                "description": "Doesn't explicitly say the return must be a boolean (True/False), not a string.",
            },
            {
                "key": "missing_single_character_handling",
                "description": "Doesn't address how to handle single-character words like 'A' or 'a'.",
            },
        ],
    },
    "p005_second_largest": {
        "flawed_prompt": (
            "Write a function second_largest(numbers) that takes a list of "
            "integers and returns the second biggest number in the list. "
            "Sort the list and pick the value just below the maximum."
        ),
        "expected_gaps": [
            {
                "key": "missing_distinct_values_rule",
                "description": "Doesn't say what to do with duplicates — e.g. for [5, 5, 4] is the second largest 5 or 4?",
            },
            {
                "key": "missing_short_list_handling",
                "description": "Doesn't specify return value for empty lists or single-element lists.",
            },
            {
                "key": "missing_input_immutability",
                "description": "Says to 'sort the list' but doesn't say not to mutate the original input.",
            },
        ],
    },
    "p010_remove_duplicates": {
        "flawed_prompt": (
            "Write a function remove_duplicates(items) that takes a list and "
            "returns a list with the duplicate values removed. You can use a "
            "set or any approach you like."
        ),
        "expected_gaps": [
            {
                "key": "missing_order_preservation",
                "description": "Doesn't require the output to preserve the order of first occurrences.",
            },
            {
                "key": "missing_set_caveat",
                "description": "Says 'use a set' which destroys order — the spec actually forbids that approach.",
            },
            {
                "key": "missing_input_immutability",
                "description": "Doesn't explicitly say not to mutate the input list.",
            },
            {
                "key": "missing_empty_list_handling",
                "description": "Doesn't specify what to return for an empty list.",
            },
        ],
    },
}


def main() -> int:
    updated = 0
    for slug, override in OVERRIDES.items():
        path = Q_DIR / f"{slug}.json"
        if not path.is_file():
            print(f"skip {slug}: file not found", file=sys.stderr)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if int(data.get("exercise_type", 0)) != 2:
            print(f"skip {slug}: exercise_type is not 2", file=sys.stderr)
            continue
        data["flawed_prompt"] = override["flawed_prompt"]
        data["expected_gaps"] = override["expected_gaps"]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"updated {slug}: {len(override['expected_gaps'])} expected_gaps")
        updated += 1

    print(f"\n{updated}/{len(OVERRIDES)} questions updated.")
    return 0 if updated == len(OVERRIDES) else 1


if __name__ == "__main__":
    sys.exit(main())
