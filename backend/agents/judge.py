"""
Coverage judge — used by Type 1 (Decompose) and Type 2 (Spot the Gap).

Given a list of student-written items and a list of expected items (each
with a `key` and `description`), the LLM decides which expected items the
student's list covers. Returns a per-key boolean map + a short reasoning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.core.llm import chat as llm_chat, extract_json


SYSTEM_PROMPT = """You are a Coverage Judge for an educational platform. The student was asked to produce a list of items (subtasks or gaps). You receive:

  - student_items: a list of natural-language items the student wrote
  - expected_items: a list of items the spec actually requires, each with a `key` and a `description`

Your job: for each expected item, decide whether ANY of the student's items covers it. "Covers" means the student's wording captures the same idea, even if the words differ. Be generous with paraphrase but strict on omission — if a key concept is missing, mark it uncovered.

Output JSON only, in exactly this shape:

{
  "covered": { "<key>": <true|false>, ... },     // one entry per expected key
  "primary_uncovered_key": "<key>" | null,        // the most important miss; null if all covered
  "reasoning": "<one-paragraph summary for the Coach; do NOT address the student directly>"
}

Rules:
- Use the EXACT expected keys; do not invent new ones.
- `primary_uncovered_key` is the single best target for a Socratic hint — usually the most fundamental missing concept.
- If everything is covered, `primary_uncovered_key` is null.
- Reasoning is one short paragraph, max 80 words, internal context only.
"""


@dataclass
class CoverageResult:
    covered: dict[str, bool]            # expected_key -> covered?
    primary_uncovered_key: str | None   # for Coach Socratic question
    reasoning: str
    raw_response: str
    input_tokens: int
    output_tokens: int

    @property
    def covered_count(self) -> int:
        return sum(1 for v in self.covered.values() if v)

    @property
    def total(self) -> int:
        return len(self.covered)

    @property
    def all_covered(self) -> bool:
        return self.total > 0 and self.covered_count == self.total


def judge_coverage(
    student_items: list[str],
    expected: list[dict[str, str]],
    *,
    kind: str = "subtask",
    max_tokens: int = 280,
) -> CoverageResult:
    """LLM judge. `kind` is "subtask" (Type 1) or "gap" (Type 2) — used only
    in the user message for context, the schema is identical.
    """
    if not expected:
        return CoverageResult(
            covered={},
            primary_uncovered_key=None,
            reasoning="(no expected items)",
            raw_response="",
            input_tokens=0,
            output_tokens=0,
        )

    valid_keys = [e["key"] for e in expected]

    user_msg = (
        f"KIND: {kind}\n\n"
        f"STUDENT'S {kind.upper()} LIST:\n"
        + "\n".join(f"- {s}" for s in (student_items or [])) + "\n\n"
        f"EXPECTED {kind.upper()}S (judge coverage of these):\n"
        + json.dumps(expected, indent=2)
        + "\n\nReturn JSON only."
    )

    res = llm_chat(
        system=SYSTEM_PROMPT,
        user=user_msg,
        max_tokens=max_tokens,
        temperature=0.2,
        response_format_json=True,
    )

    try:
        parsed = extract_json(res.text)
    except ValueError:
        # Fallback: assume nothing is covered if we can't parse.
        return CoverageResult(
            covered={k: False for k in valid_keys},
            primary_uncovered_key=valid_keys[0] if valid_keys else None,
            reasoning=f"Judge LLM unparseable. Raw: {res.text[:160]!r}",
            raw_response=res.text,
            input_tokens=res.input_tokens,
            output_tokens=res.output_tokens,
        )

    raw_covered = parsed.get("covered", {}) or {}
    covered = {k: bool(raw_covered.get(k, False)) for k in valid_keys}

    primary = parsed.get("primary_uncovered_key")
    if primary is not None and primary not in covered:
        primary = None
    if primary is None and not all(covered.values()):
        # fill in best-effort: pick the first uncovered key
        primary = next((k for k, v in covered.items() if not v), None)

    reasoning = str(parsed.get("reasoning") or "").strip() or "(no reasoning)"

    return CoverageResult(
        covered=covered,
        primary_uncovered_key=primary,
        reasoning=reasoning,
        raw_response=res.text,
        input_tokens=res.input_tokens,
        output_tokens=res.output_tokens,
    )


__all__ = ["judge_coverage", "CoverageResult"]
