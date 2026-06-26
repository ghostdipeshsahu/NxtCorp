from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import settings


class QuestionNotFoundError(KeyError):
    pass


def _questions_root() -> Path:
    return Path(settings.questions_dir).resolve()


def question_path(question_id: str) -> Path:
    if not question_id.replace("_", "").isalnum():
        # cheap guard against path traversal — ids should be snake_case ascii
        raise QuestionNotFoundError(question_id)
    return _questions_root() / f"{question_id}.json"


# v4 schema-bridge: new question files use `id: "p001"` + string
# `exercise_type: "type_1"` + `reference_solution` + `real_gaps` (and a few
# other field-name changes). Older callers still read the legacy fields
# (`question_id`, integer `exercise_type`, `reference_code`, `gap_taxonomy`,
# `expected_subtasks`, `expected_gaps`, `failing_inputs_hint`). This
# normalizer maps new → legacy in-memory at load time so the rest of the
# codebase doesn't need a rewrite.

_TYPE_STR_TO_INT = {
    "type_1": 1, "type_2": 2, "type_3": 3, "type_4": 4, "type_5": 5,
}


def _slugify(text: str) -> str:
    """Lowercase + underscores. Used to mint stable gap_taxonomy keys from
    the human-readable `gap` titles in `real_gaps`.
    """
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s or "gap"


def _normalize_question(data: dict[str, Any], filename_stem: str) -> dict[str, Any]:
    """Map v4 schema fields to the legacy field names the runtime reads.

    - `id` ("p001") + filename → `question_id` ("p001_bonus_calculator")
    - `exercise_type` string ("type_1") → integer (1)
    - `reference_solution` → `reference_code` (executor input)
    - `real_gaps[]` → synthetic `gap_taxonomy[]` (Zara taxonomy)
    - `reference_decomposition` → `expected_subtasks` (T2 coverage source)
    - `reference_failure_cases` → `expected_gaps` (T3 coverage source)
    - `reference_bugs` → `expected_gaps` (T4 coverage source if missing)
    - `original_broken_prompt` → `failing_prompt` (T5 surface)
    - `ai_prompt_shown` → `flawed_prompt` (T3 surface)
    - `buggy_ai_code` → `target_code` (T4 verify surface)
    - `failing_inputs_hint` left untouched (or derived from failing_tests)

    All new fields are also retained alongside so future code can read them
    natively without going through the bridge.
    """
    q = dict(data)  # shallow copy; we don't want to mutate the lru_cache value

    # --- question_id ---
    if not q.get("question_id"):
        q["question_id"] = filename_stem

    # --- exercise_type → int ---
    et = q.get("exercise_type")
    if isinstance(et, str):
        q["exercise_type"] = _TYPE_STR_TO_INT.get(et.lower().strip(), 1)

    # --- reference_solution → reference_code ---
    if "reference_code" not in q and "reference_solution" in q:
        q["reference_code"] = q["reference_solution"]

    # --- real_gaps → gap_taxonomy (synth) ---
    if not q.get("gap_taxonomy") and isinstance(q.get("real_gaps"), list):
        primary_skill = q.get("primary_skill") or "edge_case"
        taxonomy = []
        for entry in q["real_gaps"]:
            if not isinstance(entry, dict):
                continue
            gap_name = entry.get("gap") or entry.get("name") or "missing rule"
            desc = entry.get("description") or gap_name
            taxonomy.append({
                "key": _slugify(gap_name),
                "description": desc,
                "skill": primary_skill,
            })
        if taxonomy:
            q["gap_taxonomy"] = taxonomy

    # --- reference_decomposition → expected_subtasks (T2) ---
    if not q.get("expected_subtasks") and isinstance(q.get("reference_decomposition"), list):
        es = []
        for item in q["reference_decomposition"]:
            if isinstance(item, dict) and item.get("key"):
                es.append(item)
            elif isinstance(item, str):
                es.append({"key": _slugify(item), "description": item})
        if es:
            q["expected_subtasks"] = es

    # --- reference_failure_cases → expected_gaps (T3) ---
    if not q.get("expected_gaps") and isinstance(q.get("reference_failure_cases"), list):
        eg = []
        for item in q["reference_failure_cases"]:
            if isinstance(item, dict) and item.get("key"):
                eg.append({**item, "skill": item.get("skill") or "edge_case"})
            elif isinstance(item, str):
                eg.append({"key": _slugify(item), "description": item, "skill": "edge_case"})
        if eg:
            q["expected_gaps"] = eg

    # --- reference_bugs → expected_gaps (T4 fallback) ---
    if not q.get("expected_gaps") and isinstance(q.get("reference_bugs"), list):
        eg = []
        for item in q["reference_bugs"]:
            if isinstance(item, dict) and item.get("key"):
                eg.append({**item, "skill": item.get("skill") or "output_verification"})
        if eg:
            q["expected_gaps"] = eg

    # --- original_broken_prompt → failing_prompt (T5) ---
    if not q.get("failing_prompt") and q.get("original_broken_prompt"):
        q["failing_prompt"] = q["original_broken_prompt"]

    # --- ai_prompt_shown → flawed_prompt (T3) ---
    if not q.get("flawed_prompt") and q.get("ai_prompt_shown"):
        q["flawed_prompt"] = q["ai_prompt_shown"]

    # --- buggy_ai_code → target_code (T4) ---
    if not q.get("target_code") and q.get("buggy_ai_code"):
        q["target_code"] = q["buggy_ai_code"]

    return q


@lru_cache(maxsize=128)
def load_question(question_id: str) -> dict[str, Any]:
    """Load the enriched JSON for a question. Raises QuestionNotFoundError if missing.

    Pulls the file by filename stem, then runs `_normalize_question` so the
    rest of the runtime can keep reading legacy field names regardless of
    whether the source file uses the v3 or v4 schema.
    """
    path = question_path(question_id)
    if not path.is_file():
        raise QuestionNotFoundError(question_id)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _normalize_question(data, filename_stem=question_id)


def clear_cache() -> None:
    load_question.cache_clear()


def function_name_from_signature(question: dict[str, Any]) -> str:
    """Pull the function name out of `function_signature` (e.g. 'def foo(x): ...' -> 'foo')."""
    sig = question.get("function_signature", "") or ""
    after_def = sig.split("def", 1)[-1].strip()
    name = after_def.split("(", 1)[0].strip()
    if not name:
        raise ValueError(f"could not parse function name from signature: {sig!r}")
    return name
