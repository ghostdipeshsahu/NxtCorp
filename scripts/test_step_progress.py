"""Progression verification.

No LLM calls. Use the DB directly to mark P001 completed, then assert
GET /api/task/current returns P002.

Run from project root:
    python -m scripts.test_step_progress
"""

from __future__ import annotations

import os
import sys
import tempfile

_fd, _DB_PATH = tempfile.mkstemp(prefix="nxtcorp_step_progress_", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from fastapi.testclient import TestClient  # noqa: E402

from backend.db.database import SessionLocal  # noqa: E402
from backend.db.models import Player, PlayerCompletedTask  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services.question_progression import (  # noqa: E402
    clear_cache,
    list_question_ids,
)


def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)


def main() -> int:
    overall_ok = True
    clear_cache()

    with TestClient(app) as client:
        section("0) Question catalog discovered from disk")
        catalog = list_question_ids()
        print(f"  found {len(catalog)} questions")
        for q in catalog:
            print(f"    {q}")
        if len(catalog) < 2:
            print("  --> FAIL: need at least p001 and p002"); return 1
        if catalog[0] != "p001_detect_capital":
            print("  --> FAIL: first should be p001"); overall_ok = False
        if catalog[1] != "p002_is_palindrome":
            print(f"  --> FAIL: second should be p002, got {catalog[1]}"); overall_ok = False

        section("1) Register fresh player")
        r = client.post(
            "/api/auth/register",
            json={
                "username": "progress_a",
                "password": "hunter2hunter2",
                "display_name": "progress_a",
                "avatar_id": "avatar_02",
            },
        )
        if r.status_code != 201:
            print(f"  --> FAIL register: {r.text}"); return 1
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        with SessionLocal() as db:
            pid = db.query(Player).filter(Player.username == "progress_a").one().id

        section("2) Fresh player -> GET /current returns p001")
        r = client.get("/api/task/current", headers=auth)
        t = r.json()
        print(f"  status={r.status_code}  question_id={t.get('question_id')}")
        if t.get("question_id") != "p001_detect_capital":
            print("  --> FAIL: should serve p001 first"); overall_ok = False

        section("3) Mark p001 completed directly in DB")
        with SessionLocal() as db:
            db.add(PlayerCompletedTask(
                player_id=pid, question_id="p001_detect_capital", attempts_taken=1
            ))
            db.commit()

        section("4) After p001 complete -> GET /current returns p002")
        r = client.get("/api/task/current", headers=auth)
        t = r.json()
        print(f"  status={r.status_code}  question_id={t.get('question_id')}  title={t.get('title')}")
        if t.get("question_id") != "p002_is_palindrome":
            print(f"  --> FAIL: expected p002, got {t.get('question_id')}"); overall_ok = False

        section("5) Mark p002 + p003 complete -> /current returns p004")
        with SessionLocal() as db:
            db.add(PlayerCompletedTask(
                player_id=pid, question_id="p002_is_palindrome", attempts_taken=1
            ))
            db.add(PlayerCompletedTask(
                player_id=pid, question_id="p003_digit_sum", attempts_taken=2
            ))
            db.commit()
        r = client.get("/api/task/current", headers=auth)
        t = r.json()
        print(f"  question_id={t.get('question_id')}")
        if t.get("question_id") != "p004_grade":
            print(f"  --> FAIL: expected p004, got {t.get('question_id')}"); overall_ok = False

        section("6) Skip-ahead resilience: mark p005 too -> still serves p004 (catalog order, not max-done)")
        with SessionLocal() as db:
            db.add(PlayerCompletedTask(
                player_id=pid, question_id="p005_second_largest", attempts_taken=1
            ))
            db.commit()
        r = client.get("/api/task/current", headers=auth)
        t = r.json()
        print(f"  question_id={t.get('question_id')}")
        if t.get("question_id") != "p004_grade":
            print(f"  --> FAIL: should still be p004 (first unfinished), got {t.get('question_id')}")
            overall_ok = False

        section("7) Sample test inputs/expected on p002 are proper JSON types")
        r = client.get("/api/task/current", headers=auth)
        # we're on p004; ask for p002 explicitly via catalog
        # Use the in-process loader to verify shape
        from backend.core.question_loader import load_question
        q2 = load_question("p002_is_palindrome")
        s0 = q2["sample_tests"][0]
        print(f"  sample[0] input={s0['input']!r} ({type(s0['input']).__name__})  expected={s0['expected']!r}")
        if not isinstance(s0["expected"], bool):
            print("  --> FAIL: expected should be a JSON bool"); overall_ok = False

        section("SUMMARY")
        print(f"  overall_ok = {overall_ok}")

    try:
        os.remove(_DB_PATH)
    except OSError:
        pass
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
