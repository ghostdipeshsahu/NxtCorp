"""One-shot: swap exercise_type numbers per v3 canonical mapping.

Old → New:
  1 (Decompose)         → 2 (Decompose Vague Work)
  2 (Spot the Gap)      → 3 (Predict AI Failure Cases)
  3 (Specify+Execute)   → 1 (Prompt AI to Build)
  4 (Verify)            → 4 (Verify AI Output)
  5 (Diagnose+Fix)      → 5 (Improve AI After Failure)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
Q_DIR = REPO_ROOT / "questions"

SWAP = {1: 2, 2: 3, 3: 1, 4: 4, 5: 5}


def main() -> int:
    files = sorted(Q_DIR.glob("p*.json"))
    if not files:
        print(f"no questions in {Q_DIR}", file=sys.stderr)
        return 2

    before: Counter = Counter()
    after: Counter = Counter()
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        old = int(data.get("exercise_type", 0))
        new = SWAP.get(old, old)
        before[old] += 1
        after[new] += 1
        if old != new:
            data["exercise_type"] = new
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  {path.name}: type {old} -> {new}")
        else:
            print(f"  {path.name}: type {old} (unchanged)")

    print()
    print("BEFORE:", dict(before))
    print("AFTER :", dict(after))
    return 0


if __name__ == "__main__":
    sys.exit(main())
