"""
One-shot adapter: GenCode question JSON -> NxtCorp question JSON.

GenCode shape (input):
  {
    "id": "P001",
    "problem_description": "...",
    "requirements": "- Logical Decomposition: ...\n- Edge Case Handling: ...\n...",
    "sample_tests":  [{"input": "'HELLO'", "expected": "True"}, ...],
    "hidden_tests":  [{"input": ...},      ...],
    "reference_solution": "...",
    "reference_prompt":   "...",
    "reference_code":     "def detect_capital(word): ..."
  }

NxtCorp shape (output) — matches questions/p001_detect_capital.json schema.

Test inputs/expected come in as Python repr strings. We literal_eval them
into actual values. Multi-arg inputs (`[1,2,3], 2`) become Python lists so
the executor's `if isinstance(inp, list): fn(*inp)` convention splats them.

Reference code is run through the existing executor against all parsed tests
before the file is written. If reference doesn't pass, we abort (no broken
question files written).

Run from project root:
    python -m scripts.import_gencode

Writes to nxtcorp/questions/, skipping files that already exist unless
--overwrite is passed.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

from backend.core.code_executor import execute
from backend.core.question_loader import function_name_from_signature


REPO_ROOT = Path(__file__).resolve().parent.parent
GENCODE_DIR = REPO_ROOT.parent / "gencode" / "questions"
NXTCORP_DIR = REPO_ROOT / "questions"


# ---------- helpers ----------

def _parse_input(s: str) -> Any:
    """Parse a test `input` string into a value the executor can use.

    The executor's convention: if `input` is a list, splat it as positional
    args; otherwise pass as a single positional arg. GenCode tests come in
    two shapes:

      single-arg: `'HELLO'`,  `[3,1,4,1,5]`,  `True`
      multi-arg : `[1,2,3], 2`,  `50, 1.7`           (top-level comma)

    For multi-arg we return a Python list, so the executor splats. For
    single-arg where the value is itself a list, we wrap one level deeper
    (`[3,1,4]` -> `[[3,1,4]]`) so the executor's splat passes the list as
    one argument. For single-arg non-list values we pass through as-is.
    """
    s = s.strip()
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"could not parse input {s!r}: {e}") from e

    if isinstance(tree.body, ast.Tuple):
        # multi-arg: literal_eval returns a tuple; convert to list for executor splat.
        return list(ast.literal_eval(s))

    # single-arg path
    value = ast.literal_eval(s)
    if isinstance(value, list):
        # wrap so executor's splat passes the list itself as ONE arg
        return [value]
    return value


def _parse_expected(s: str) -> Any:
    """Expected value — straight Python literal, no arity wrapping."""
    return ast.literal_eval(s.strip())


def _parse_tests(raw_tests: list[dict]) -> list[dict]:
    out: list[dict] = []
    for t in raw_tests or []:
        try:
            inp = _parse_input(t["input"])
            exp = _parse_expected(t["expected"])
        except Exception as e:
            raise ValueError(f"could not parse test {t!r}: {e}") from e
        item: dict[str, Any] = {"input": inp, "expected": exp}
        if t.get("description"):
            item["description"] = t["description"]
        out.append(item)
    return out


def _extract_signature(reference_code: str) -> str:
    """Return the function signature line (def name(...): )."""
    m = re.search(r"^(def\s+\w+\s*\([^)]*\)(?:\s*->\s*[^:]+)?)\s*:", reference_code, re.MULTILINE)
    if not m:
        raise ValueError(f"could not find function signature in reference_code: {reference_code[:100]!r}")
    return m.group(1) + ":"


def _slug_to_title(slug: str) -> str:
    # "p001_detect_capital" -> "Detect capital"
    parts = slug.split("_", 1)
    if len(parts) == 2:
        slug = parts[1]
    return slug.replace("_", " ").strip().capitalize()


# Keyword → skill heuristic for converting GenCode "requirements" lines into
# a gap_taxonomy entry.
_SKILL_KEYWORDS = [
    ("edge case", "edge_case"),
    ("boundary", "edge_case"),
    ("empty", "edge_case"),
    ("single", "edge_case"),
    ("invalid", "edge_case"),
    ("decomposition", "decomposition"),
    ("step", "decomposition"),
    ("logic", "decomposition"),
    ("validation", "requirement_completeness"),
    ("specification", "requirement_completeness"),
    ("bias", "requirement_completeness"),
    ("default", "requirement_completeness"),
    ("output", "output_verification"),
    ("format", "output_verification"),
    ("return", "output_verification"),
    ("type", "output_verification"),
    ("refine", "iterative_refinement"),
    ("iterate", "iterative_refinement"),
]


def _skill_for(text: str) -> str:
    lo = text.lower()
    for kw, skill in _SKILL_KEYWORDS:
        if kw in lo:
            return skill
    return "requirement_completeness"


def _slugify_gap_key(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return s or "gap"


def _parse_requirements(requirements: Any) -> list[dict[str, str]]:
    """Convert the GenCode `requirements` field (string or list) into a
    gap_taxonomy list of {key, description, skill} dicts.
    """
    if not requirements:
        return []
    # Normalize to list of bullet strings.
    if isinstance(requirements, str):
        lines = [l.strip() for l in requirements.splitlines() if l.strip()]
    elif isinstance(requirements, list):
        lines = [str(l).strip() for l in requirements if str(l).strip()]
    else:
        return []

    gaps: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for ln in lines:
        ln = ln.lstrip("-•* ").strip()
        if not ln:
            continue
        if ":" in ln:
            label, _, descr = ln.partition(":")
            label = label.strip()
            descr = descr.strip()
        else:
            label = ln[:40]
            descr = ln
        skill = _skill_for(label + " " + descr)
        key = "missing_" + _slugify_gap_key(label)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        gaps.append({
            "key": key,
            "description": f"Prompt under-specifies: {descr[:140]}",
            "skill": skill,
        })
    # Limit to 5 — the schema validator (author.validate_question) caps at 8
    # but we keep it tight.
    return gaps[:5] or [
        {
            "key": "missing_general_specification",
            "description": "Prompt is too vague to produce correct code.",
            "skill": "requirement_completeness",
        }
    ]


def _skill_focus_for(gaps: list[dict[str, str]]) -> list[str]:
    """Pick 1-2 distinct skills the gaps stress most."""
    counts: dict[str, int] = {}
    for g in gaps:
        counts[g["skill"]] = counts.get(g["skill"], 0) + 1
    order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    keys = [k for k, _ in order][:2]
    if not keys:
        return ["requirement_completeness"]
    return keys


def _difficulty_for(index_1based: int) -> str:
    if index_1based <= 5:
        return "easy"
    if index_1based <= 10:
        return "easy"
    return "medium"


def _framing_for(title: str) -> dict[str, str]:
    return {
        "character": "priya",
        "expression": "happy",
        "message": (
            f"Next ticket: {title}. The client needs this small piece. "
            "Take a look — write the spec exactly as you want the AI to "
            "build it, and let me know if anything's unclear."
        ),
    }


# ---------- main conversion ----------

def convert_one(src_path: Path) -> dict[str, Any]:
    raw = json.loads(src_path.read_text(encoding="utf-8"))
    slug = src_path.stem  # e.g. "p001_detect_capital"
    title = _slug_to_title(slug)

    sample_tests = _parse_tests(raw.get("sample_tests") or [])
    hidden_tests = _parse_tests(raw.get("hidden_tests") or [])

    function_signature = _extract_signature(raw["reference_code"])
    gap_taxonomy = _parse_requirements(raw.get("requirements"))
    skill_focus = _skill_focus_for(gap_taxonomy)
    # Derive a 1-based index from filename slug "p001" -> 1
    try:
        idx = int(re.match(r"p(\d+)", slug).group(1))
    except (AttributeError, ValueError):
        idx = 1

    return {
        "question_id": slug,
        "exercise_type": 3,
        "title": title,
        "difficulty": _difficulty_for(idx),
        "skill_focus": skill_focus,
        "framing": _framing_for(title),
        "problem_description": raw.get("problem_description", "").strip(),
        "function_signature": function_signature,
        "notes": "Inputs follow the description literally. No validation needed.",
        "sample_tests": sample_tests,
        "hidden_tests": hidden_tests,
        "reference_prompt": raw.get("reference_prompt", "").strip(),
        "reference_code": raw.get("reference_code", "").strip(),
        "gap_taxonomy": gap_taxonomy,
    }


def verify(q: dict[str, Any]) -> tuple[bool, str]:
    fn_name = function_name_from_signature(q)
    all_tests = list(q.get("sample_tests") or []) + list(q.get("hidden_tests") or [])
    if not all_tests:
        return (False, "no tests")
    res = execute(q["reference_code"], fn_name, all_tests, timeout_seconds=8)
    if res.setup_error:
        return (False, f"setup_error: {res.setup_error}")
    if res.timed_out:
        return (False, "timeout")
    if not res.all_passed:
        failed = [o.input for o in res.outcomes if not o.passed]
        return (False, f"{res.num_passed}/{res.num_total}; failed: {failed!r}")
    return (True, f"{res.num_passed}/{res.num_total}")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gencode-dir", default=str(GENCODE_DIR))
    p.add_argument("--output-dir", default=str(NXTCORP_DIR))
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    src_dir = Path(args.gencode_dir)
    dst_dir = Path(args.output_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(src_dir.glob("p*.json"))
    if not sources:
        print(f"no GenCode questions found in {src_dir}", file=sys.stderr)
        return 2

    print(f"converting {len(sources)} questions from {src_dir} -> {dst_dir}")
    print()

    ok_count = 0
    fail_count = 0
    for src in sources:
        dst = dst_dir / src.name
        try:
            q = convert_one(src)
        except Exception as e:
            print(f"  {src.name}: CONVERT-FAIL: {e}")
            fail_count += 1
            continue
        ok, summary = verify(q)
        if not ok:
            print(f"  {src.name}: VERIFY-FAIL: {summary}")
            fail_count += 1
            continue
        if dst.exists() and not args.overwrite:
            print(f"  {src.name}: SKIP (exists; use --overwrite). reference: {summary}")
            continue
        if args.dry_run:
            print(f"  {src.name}: OK (dry-run, not written). reference: {summary}")
        else:
            dst.write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  {src.name}: WROTE {dst}  reference: {summary}")
        ok_count += 1

    print()
    print(f"done. {ok_count} ok, {fail_count} fail.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
