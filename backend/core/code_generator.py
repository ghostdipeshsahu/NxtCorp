"""
Code Generator (step 3).

Takes a student-written prompt and a question definition, calls Claude with
a system prompt that enforces *literal* code generation — implement only
what the student specified, infer nothing — and returns raw Python source.

Why literal: this is the whole pedagogy. If the model "helpfully" fills in
the all-lowercase branch the student forgot, hidden tests pass and the
student never learns the lesson. The system prompt is therefore engineered
to behave like a junior engineer who follows the spec exactly, asks no
questions, and leaves out anything not requested.

Defaults:
- model: claude-sonnet-4-6 (spec §9)
- thinking: disabled — reasoning encourages gap-filling, which is the
  opposite of what we want
- prompt caching: enabled on the (static) system prompt to keep cost down
  across thousands of student attempts
- output parsing: strips ```python ... ``` fences and ignores any prose
  the model emits around the code block
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from backend.core.llm import chat as llm_chat


SYSTEM_PROMPT = (
    "You are a Python code generator. "
    "Write a Python function based only on the instructions given. "
    "Do not assume any requirements not explicitly stated. "
    "Do not add any logic not mentioned. "
    "Implement exactly what is described — nothing more, nothing less."
)


_FENCE_RE = re.compile(
    r"^\s*```(?:python|py)?\s*\n?(.*?)```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _strip_fences(text: str) -> str:
    """Remove leading/trailing ```python ... ``` fences if present."""
    m = _FENCE_RE.match(text.strip())
    if m:
        return m.group(1).strip()
    return text.strip()


def _extract_code(raw: str) -> str:
    """Pull Python source out of the model's response.

    Strategy:
      1. If the whole response is wrapped in a ```python ... ``` fence, peel it.
      2. Otherwise, look for the first fenced block in the body and return it.
      3. Otherwise, return the raw text trimmed.
    """
    raw = raw.strip()

    stripped = _strip_fences(raw)
    if stripped != raw:
        return stripped

    # find any fenced block inside the body
    inner = re.search(r"```(?:python|py)?\s*\n(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if inner:
        return inner.group(1).strip()

    return raw


@dataclass
class GenerationResult:
    code: str
    raw_response: str
    input_tokens: int
    output_tokens: int
    # Cache fields kept for backwards compatibility with callers and tests;
    # OpenAI-compat endpoint doesn't surface cache hits, so these are 0.
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


def build_user_message(
    student_prompt: str,
    function_signature: str,
) -> str:
    """Code Generator receives ONLY the student's prompt and the function
    signature — nothing else from the task definition. Any leakage of
    task context (description, rules, reference solution, notes, tests)
    would let the model fill gaps the student left, which defeats the
    pedagogy.
    """
    return (
        "student_prompt:\n"
        f"{student_prompt.strip()}\n"
        "\n"
        f"function_signature: {function_signature}"
    )


def generate_code(
    student_prompt: str,
    question: dict[str, Any],
    *,
    max_tokens: int = 300,
) -> GenerationResult:
    """Convert `student_prompt` into Python source via the configured LLM.

    From `question` this reads ONLY `function_signature`. No description,
    no notes, no reference prompt, no reference code, no tests, no title
    — anything else from the task would leak context and let the model
    paper over gaps in the student's spec.
    """
    function_signature = question.get("function_signature", "")
    if not function_signature:
        raise ValueError("question is missing 'function_signature'")

    user_text = build_user_message(student_prompt, function_signature)
    result = llm_chat(
        system=SYSTEM_PROMPT,
        user=user_text,
        max_tokens=max_tokens,
        temperature=0.1,  # tight, literal output
    )
    code = _extract_code(result.text)
    return GenerationResult(
        code=code,
        raw_response=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


__all__ = ["generate_code", "GenerationResult", "SYSTEM_PROMPT", "build_user_message"]
