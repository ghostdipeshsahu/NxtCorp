"""
Client Task Agent (v3 — replaces and extends scripts/author.py).

What changed from the v2 Author Agent
-------------------------------------
1. **Dual personalization.** The agent takes the student's *job role* AND
   their *weakest skill* and uses both to shape the generated task:
     - job_role chooses the FLAVOR (a data_analyst sees dataframe-shaped
       tasks, a devops_engineer sees scripting/parsing tasks, etc.)
     - weakest_skill chooses the PEDAGOGICAL TARGET — the gap_taxonomy
       is biased toward gaps in that skill so the next task stresses it.
2. **3-eval self-check loop.** After the LLM emits a candidate task, the
   agent re-prompts itself (up to 3 times) to evaluate the candidate
   against a fixed rubric (precision, gap-skill alignment, role fit,
   executable code). If the eval flags a problem, the agent regenerates
   with the critique as additional context. After 3 evaluations the best
   candidate is returned even if not perfect.

The runtime contract (output shape, hidden_tests, gap_taxonomy, etc.) is
unchanged from author.py — this module reuses the same validators and
sample-execution verifier.

This is an offline / authoring script, not a runtime path. The runtime
serves pre-enriched questions from `questions/*.json`. Use this script to
GENERATE those files for a specific (role, weakest_skill) combination.

Usage
-----
    python -m scripts.client_task_agent \\
        --role data_analyst --weakest-skill edge_case \\
        --question-id p016_revenue_outlier \\
        --signature "def find_revenue_outliers(rows: list[dict]) -> list[dict]" \\
        --output questions/p016_revenue_outlier.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from backend.core.code_executor import execute
from backend.core.llm import chat as llm_chat, extract_json
from backend.core.question_loader import function_name_from_signature
from backend.models.schemas import JOB_ROLE_LABELS, JOB_ROLES, SKILL_KEYS

# We deliberately import the author module's prompt + validators so the
# output shape stays in lock-step with the v2 enrichment pipeline.
from scripts.author import (
    EXAMPLE_QUESTION,
    REQUIRED_KEYS,
    VALID_SKILLS,
    validate_question,
)


# ---------- Role + skill briefing snippets ----------

ROLE_FLAVOR: dict[str, str] = {
    "software_developer": (
        "Frame the task as a generic application-code problem: string parsing, "
        "list manipulation, classic algorithm. Neutral business setting."
    ),
    "data_analyst": (
        "Frame the task as analyzing tabular data — e.g. lists of dicts or "
        "rows pulled from a CSV. Inputs should look like real business data "
        "(revenue, headcount, dates, customer IDs). Outputs are usually "
        "aggregations, filtered lists, or single summary values."
    ),
    "genai_engineer": (
        "Frame the task as something a GenAI engineer would actually build: "
        "post-processing LLM output, parsing structured responses, validating "
        "a JSON contract, scoring text. Avoid making it about \"calling an LLM\" "
        "— the function itself should be pure logic over text/dict inputs."
    ),
    "qa_engineer": (
        "Frame the task as a verification problem — given some data, return "
        "what's wrong with it, or assert a property holds. The function "
        "shape often returns a list of problems or a boolean."
    ),
    "devops_engineer": (
        "Frame the task as parsing config / logs / paths — string-heavy work "
        "over inputs that look like real ops data (file paths, log lines, env "
        "var lists, key-value pairs)."
    ),
}


SKILL_TARGET: dict[str, str] = {
    "decomposition": (
        "The gap_taxonomy MUST stress decomposition: students under-spec by "
        "lumping multiple sub-steps into one vague rule. Hidden tests should "
        "expose attempts that skip an intermediate transformation step."
    ),
    "edge_case": (
        "The gap_taxonomy MUST stress edge cases: empty inputs, all-of-one-type, "
        "boundary values, off-by-one, negatives, unicode. Hidden tests must "
        "probe each named edge category."
    ),
    "requirement_completeness": (
        "The gap_taxonomy MUST stress completeness: at least one full required "
        "rule that a hasty student will omit, AND one tie-breaker / format rule "
        "they'll leave to the AI's guesswork. Hidden tests must catch both."
    ),
    "output_verification": (
        "The gap_taxonomy MUST stress output verification: the reference_code "
        "should look superficially plausible but differ from the reference_prompt "
        "in a subtle way that only careful test-writing would catch."
    ),
    "iterative_refinement": (
        "The gap_taxonomy MUST stress iterative refinement: gaps should map "
        "cleanly to specific failing inputs the student can use to tighten their "
        "spec on a second attempt."
    ),
    "prompt_optimization": (
        "Treat this like requirement_completeness — Phase 4 (prompt_optimization) "
        "is not active in the runtime, so author for completeness as a stand-in."
    ),
}


def _role_label(role: str) -> str:
    return JOB_ROLE_LABELS.get(role, "Software Developer")


# ---------- Prompt construction ----------

def _build_system_prompt(role: str, weakest_skill: str, phase: str = "1",
                          sequence: int = 1, exercise_type: str = "type_1") -> str:
    """v6 Client Task Agent. Caller supplies phase/sequence/exercise_type
    as runtime context (the agent treats these as 'game state' it knows,
    not as student-facing input). The agent's only conceptual input is
    job_role.
    """
    type_label = {
        "type_1": "Type 1 (Prompt AI to Build)",
        "type_2": "Type 2 (Decompose Vague Work)",
        "type_3": "Type 3 (Predict AI Failure)",
        "type_4": "Type 4 (Verify AI Output)",
        "type_5": "Type 5 (Improve AI After Failure)",
    }.get(exercise_type, exercise_type)

    return f"""You are the Client Task Agent at NxtCorp.

You generate workplace tasks for students based on their job role.

You know the current game state:
- Current phase: {phase}
- Current sequence position: {sequence}
- Current exercise type for this position: {type_label}
  Phase 1 sequence:
  Position 1 → Type 1 (Prompt AI to Build)
  Position 2 → Type 2 (Decompose Vague Work)
  Position 3 → Type 3 (Predict AI Failure)
  Position 4 → Type 4 (Verify AI Output)
  Position 5 → Type 5 (Improve AI After Failure)

You receive:
- job_role: the student's chosen role ({_role_label(role)})

Your job:
Generate a complete task that feels like real work for that job role at that exercise type.

Every task must have:
1. A realistic workplace scenario — something that actually happens at a tech company
2. A meeting script with 3-4 characters speaking conversationally
3. Meeting rules delivered in business language — not technical specification
4. At least 2 genuine real-world gaps that business people naturally forget to mention
5. A function signature appropriate for the exercise type
6. For Type 1 and 5: the scenario must have rules that require computational translation — not just copying

Meeting script rules:
- Characters speak naturally
- No character summarises at the end
- Rules are incomplete by design — gaps exist because business people genuinely forget, not because you manufactured them
- Gaps must be resolvable by a first year student with common sense and careful thinking

Output format:
{{
  "title": "...",
  "exercise_type": "{exercise_type}",
  "scenario": "...",
  "meeting_script": [...],
  "function_signature": "...",
  "notes": "..."
}}

SELF-EVALUATION — run before finalising:

Check 1: Can student pass by copying meeting rules directly into prompt?
If yes: redesign the gaps so copying fails.

Check 2: Are gaps genuinely realistic?
If any gap is impossible in real business (like zero salary, impossible combinations): remove it and replace with a real one.

Check 3: Does the scenario feel like real work for the job role?
If it could be any role: add specific job role context.

If any check fails: regenerate that part and check again.
Maximum 3 retries.

## Role flavor (background — for {_role_label(role)})

{ROLE_FLAVOR.get(role, ROLE_FLAVOR['software_developer'])}

Return JSON only. Start with {{ and end with }}.
"""


def _build_user_message(
    question_id: str,
    function_signature: str,
    extra_hint: Optional[str],
) -> str:
    parts = [
        f"question_id: {question_id}",
        f"function_signature: {function_signature}",
        "",
        "Author the enriched question. Pass question_id and function_signature through verbatim.",
    ]
    if extra_hint:
        parts.extend(["", "ADDITIONAL DIRECTION (from previous evaluation):", extra_hint])
    parts.append("")
    parts.append("Return JSON only.")
    return "\n".join(parts)


# ---------- Self-check loop ----------

EVAL_SYSTEM = """You are the **Evaluator** for the Client Task Agent. You read a candidate enriched question and decide whether it meets the bar.

Score each axis 0-5:
  - role_fit: does the framing feel native to the student's job role?
  - skill_target: does at least one gap entry target the student's weakest skill, and do hidden tests actually expose it?
  - precision: is the reference_prompt unambiguous? Would a student writing it produce passing code?
  - executable: is the reference_code present, syntactically valid, and self-consistent with reference_prompt?
  - completeness: are required keys present with reasonable values?

Return JSON only:

{
  "scores": { "role_fit": <0-5>, "skill_target": <0-5>, "precision": <0-5>, "executable": <0-5>, "completeness": <0-5> },
  "overall": <0-25>,
  "verdict": "accept" | "revise",
  "critique": "<short paragraph telling the author what to fix; empty if accept>"
}

Accept iff overall >= 20 AND each axis >= 3. Otherwise revise.
"""


def _evaluate(candidate: dict[str, Any], role: str, weakest_skill: str) -> dict[str, Any]:
    user = json.dumps({
        "candidate": candidate,
        "role": role,
        "weakest_skill": weakest_skill,
    }, indent=2)
    result = llm_chat(
        system=EVAL_SYSTEM,
        user=user,
        max_tokens=400,
        temperature=0.1,
        response_format_json=True,
    )
    try:
        return extract_json(result.text)
    except ValueError:
        return {
            "scores": {},
            "overall": 0,
            "verdict": "revise",
            "critique": "Evaluator returned unparseable output.",
        }


def _generate_once(
    role: str,
    weakest_skill: str,
    question_id: str,
    function_signature: str,
    extra_hint: Optional[str] = None,
    temperature: float = 0.7,
) -> dict[str, Any]:
    result = llm_chat(
        system=_build_system_prompt(role, weakest_skill),
        user=_build_user_message(question_id, function_signature, extra_hint),
        max_tokens=2400,
        temperature=temperature,
        response_format_json=True,
    )
    return extract_json(result.text)


def generate_task(
    *,
    role: str,
    weakest_skill: str,
    question_id: str,
    function_signature: str,
    max_evals: int = 3,
) -> dict[str, Any]:
    """Generate a task with a 3-iteration self-check loop.

    Returns the best candidate seen across the loop. Raises only if every
    candidate fails basic schema validation.
    """
    if role not in JOB_ROLES:
        raise ValueError(f"unknown role: {role}; must be one of {JOB_ROLES}")
    if weakest_skill not in SKILL_KEYS:
        raise ValueError(f"unknown skill: {weakest_skill}; must be one of {SKILL_KEYS}")

    best: Optional[dict[str, Any]] = None
    best_overall = -1
    critique: Optional[str] = None

    for i in range(max_evals):
        try:
            candidate = _generate_once(
                role, weakest_skill, question_id, function_signature,
                extra_hint=critique,
                temperature=0.7 if i == 0 else 0.5,
            )
        except ValueError as e:
            critique = f"Previous attempt produced unparseable JSON ({e}). Emit valid JSON only this time."
            continue

        schema_errors = validate_question(candidate)
        if schema_errors:
            critique = "Schema errors to fix: " + "; ".join(schema_errors)
            # Still consider this candidate if no better one exists yet.
            if best is None:
                best = candidate
                best_overall = 0
            continue

        eval_out = _evaluate(candidate, role, weakest_skill)
        overall = int(eval_out.get("overall", 0))
        if overall > best_overall:
            best = candidate
            best_overall = overall

        if eval_out.get("verdict") == "accept":
            return candidate

        critique = str(eval_out.get("critique") or "Improve precision and role fit.")

    if best is None:
        raise RuntimeError("Client Task Agent failed to produce a valid candidate after 3 attempts.")
    return best


# ---------- Verifier (re-uses author.py's pattern) ----------

def _verify_reference_passes(question: dict[str, Any]) -> list[str]:
    """Run reference_code against every test; return list of failure messages."""
    code = question.get("reference_code") or ""
    fn_name = function_name_from_signature(question)
    tests = (question.get("sample_tests") or []) + (question.get("hidden_tests") or [])
    if not code or not tests:
        return ["reference_code or tests missing — cannot verify"]
    res = execute(code, fn_name, tests, timeout_seconds=5)
    if res.setup_error:
        return [f"setup_error: {res.setup_error}"]
    if res.timed_out:
        return ["reference_code timed out"]
    fails = [
        f"input={o.input!r} expected={o.expected!r} actual={o.actual!r}"
        for o in res.outcomes
        if not o.passed
    ]
    return fails


# ---------- CLI ----------

def main() -> int:
    p = argparse.ArgumentParser(description="Generate a personalized task for a specific student.")
    p.add_argument("--role", required=True, choices=list(JOB_ROLES), help="Student's job role.")
    p.add_argument("--weakest-skill", required=True, choices=list(SKILL_KEYS), help="Skill to stress.")
    p.add_argument("--question-id", required=True, help="snake_case ID, e.g. p016_revenue_outlier.")
    p.add_argument("--signature", required=True, help="def name(args) -> return_type")
    p.add_argument("--output", type=Path, help="Where to write the JSON (defaults to stdout).")
    p.add_argument("--max-evals", type=int, default=3)
    p.add_argument("--no-verify", action="store_true", help="Skip running reference_code through the executor.")
    args = p.parse_args()

    q = generate_task(
        role=args.role,
        weakest_skill=args.weakest_skill,
        question_id=args.question_id,
        function_signature=args.signature,
        max_evals=args.max_evals,
    )

    schema_errors = validate_question(q)
    if schema_errors:
        print("SCHEMA ERRORS:", file=sys.stderr)
        for e in schema_errors:
            print(f"  - {e}", file=sys.stderr)
        return 2

    if not args.no_verify:
        fails = _verify_reference_passes(q)
        if fails:
            print("REFERENCE CODE FAILS ITS OWN TESTS:", file=sys.stderr)
            for f in fails:
                print(f"  - {f}", file=sys.stderr)
            return 3

    blob = json.dumps(q, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(blob, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
