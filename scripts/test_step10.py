"""Step 10 verification — story event engine.

No LLM calls. We insert Attempt rows directly into the DB to simulate
player history, then exercise the story endpoints.

Scenarios:
  A) Fresh player after onboarding: no events yet (prereqs unmet too)
  B) Mark day1 events seen + insert a passing Attempt -> Day 3 Arjun fires
  C) Insert a failing Attempt with primary_gap -> Day 10 Zara fires
  D) advance(day3) grants XP and marks seen
  E) advance(day3) again -> no double-XP
  F) advance with skipped=True -> no XP, still marked seen
  G) Full progression: 5 attempts + prereq events seen -> end_of_week fires

Run from project root:
    python -m scripts.test_step10
"""

from __future__ import annotations

import os
import sys
import tempfile

_fd, _DB_PATH = tempfile.mkstemp(prefix="nxtcorp_step10_", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from fastapi.testclient import TestClient  # noqa: E402

from backend.db.database import SessionLocal  # noqa: E402
from backend.db.models import Attempt, Player, PlayerStoryEvent  # noqa: E402
from backend.main import app  # noqa: E402


def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)


def register(client: TestClient, username: str) -> tuple[int, str]:
    r = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "hunter2hunter2",
            "display_name": username,
            "avatar_id": "avatar_02",
        },
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    with SessionLocal() as db:
        pid = db.query(Player).filter(Player.username == username).one().id
    return pid, token


def mark_onboarding_seen(player_id: int) -> None:
    """Simulate the onboarding endpoint having recorded the Day 1 prereqs."""
    with SessionLocal() as db:
        for key in ("day1_priya_welcome", "day1_arjun_intro"):
            db.add(PlayerStoryEvent(player_id=player_id, event_key=key))
        db.commit()


def insert_attempt(player_id: int, *, all_passed: bool, primary_gap=None) -> None:
    with SessionLocal() as db:
        db.add(
            Attempt(
                player_id=player_id,
                question_id="p001_detect_capital",
                attempt_number=1,
                exercise_type=3,
                student_prompt="(synthetic test)",
                generated_code="def detect_capital(w): return True",
                all_passed=all_passed,
                primary_gap=primary_gap,
                xp_earned=0,
            )
        )
        db.commit()


def pending_keys(payload):
    return [e["event_key"] for e in payload["pending_events"]]


def main() -> int:
    overall_ok = True

    with TestClient(app) as client:
        pid, token = register(client, "rookie_step10")
        auth = {"Authorization": f"Bearer {token}"}

        # ===== A) Fresh state: nothing should fire =====
        section("A) Fresh player (no onboarding, no attempts) -> no pending events")
        r = client.get("/api/story/current", headers=auth)
        st = r.json()
        print(f"  status={r.status_code}  act={st['act']}  day={st['day']}  pending={pending_keys(st)}")
        if st["pending_events"]:
            print("  --> FAIL: should be empty before onboarding/attempts"); overall_ok = False

        # ===== B) Onboarding + passing attempt -> Day 3 fires =====
        section("B) Onboarding seen + 1 passing attempt -> act1_day3_arjun_congrats")
        mark_onboarding_seen(pid)
        insert_attempt(pid, all_passed=True)
        r = client.get("/api/story/current", headers=auth)
        st = r.json()
        print(f"  pending: {pending_keys(st)}")
        if "act1_day3_arjun_congrats" not in pending_keys(st):
            print("  --> FAIL: Day 3 should fire"); overall_ok = False
        # Day 5 should NOT fire yet (only 1 attempt, prereq day3 unseen)
        if "act1_day5_ravi_nice_work" in pending_keys(st):
            print("  --> FAIL: Day 5 shouldn't fire before day3 is seen"); overall_ok = False
        # Inspect the event payload
        day3 = next(e for e in st["pending_events"] if e["event_key"] == "act1_day3_arjun_congrats")
        print(f"  title='{day3['title']}'  messages={len(day3['messages'])}  xp_bonus={day3['xp_bonus']}")
        if len(day3["messages"]) < 1 or day3["xp_bonus"] != 20:
            print("  --> FAIL: bad event shape"); overall_ok = False
        # Personalization?
        body = day3["messages"][0]["body"]
        if "rookie_step10" not in body:
            print(f"  --> FAIL: body should be personalized with display_name (got: {body[:80]!r})")
            overall_ok = False

        # ===== C) Failure with primary_gap -> Zara QA fires =====
        section("C) Failure with primary_gap -> act1_day10_zara_first_qa")
        insert_attempt(pid, all_passed=False, primary_gap="missing_all_lower_case")
        r = client.get("/api/story/current", headers=auth)
        st = r.json()
        print(f"  pending: {pending_keys(st)}")
        if "act1_day10_zara_first_qa" not in pending_keys(st):
            print("  --> FAIL: Zara QA event should fire"); overall_ok = False

        # ===== D) advance(day3) grants XP =====
        section("D) advance(day3) -> grants 20 XP + marks seen")
        prof_before = client.get("/api/player/profile", headers=auth).json()
        xp_before = prof_before["total_xp"]
        r = client.post(
            "/api/story/advance",
            headers=auth,
            json={"event_key": "act1_day3_arjun_congrats", "skipped": False},
        )
        adv = r.json()
        print(f"  resp: {adv}")
        if adv["xp_awarded"] != 20:
            print("  --> FAIL: should award 20 XP"); overall_ok = False
        if adv["story_day"] != 3:
            print("  --> FAIL: story_day should be 3 after this event"); overall_ok = False
        prof_after = client.get("/api/player/profile", headers=auth).json()
        if prof_after["total_xp"] != xp_before + 20:
            print(f"  --> FAIL: total_xp didn't bump by 20 ({xp_before} -> {prof_after['total_xp']})")
            overall_ok = False

        # Check it's no longer in pending
        r = client.get("/api/story/current", headers=auth)
        if "act1_day3_arjun_congrats" in pending_keys(r.json()):
            print("  --> FAIL: should no longer be pending"); overall_ok = False

        # ===== E) advance again -> no double XP =====
        section("E) advance(day3) again -> no double-XP")
        prof_before = client.get("/api/player/profile", headers=auth).json()
        r = client.post(
            "/api/story/advance",
            headers=auth,
            json={"event_key": "act1_day3_arjun_congrats", "skipped": False},
        )
        adv = r.json()
        prof_after = client.get("/api/player/profile", headers=auth).json()
        print(f"  resp: {adv}  total_xp before={prof_before['total_xp']}  after={prof_after['total_xp']}")
        # advance is idempotent on already-seen — xp_awarded may still report 20 (bonus would be paid if we re-granted) but DB shouldn't change. Verify XP unchanged.
        # Currently our impl pays bonus even on re-call if def is found; that's a bug. Check behavior.
        if prof_after["total_xp"] != prof_before["total_xp"]:
            print(f"  --> FAIL: XP changed on re-advance ({prof_before['total_xp']} -> {prof_after['total_xp']})")
            overall_ok = False

        # ===== F) Skip flag -> no XP =====
        section("F) advance(zara, skipped=true) -> no XP, marked seen")
        prof_before = client.get("/api/player/profile", headers=auth).json()
        r = client.post(
            "/api/story/advance",
            headers=auth,
            json={"event_key": "act1_day10_zara_first_qa", "skipped": True},
        )
        adv = r.json()
        prof_after = client.get("/api/player/profile", headers=auth).json()
        print(f"  resp: {adv}  total_xp before={prof_before['total_xp']}  after={prof_after['total_xp']}")
        if adv["xp_awarded"] != 0:
            print("  --> FAIL: skip should award 0 XP"); overall_ok = False
        if prof_after["total_xp"] != prof_before["total_xp"]:
            print("  --> FAIL: total_xp shouldn't move on skip"); overall_ok = False
        # Marked seen?
        r = client.get("/api/story/current", headers=auth)
        if "act1_day10_zara_first_qa" in pending_keys(r.json()):
            print("  --> FAIL: zara event should no longer be pending after skip"); overall_ok = False

        # ===== G) Full progression -> end_of_week eventually fires =====
        section("G) Add more attempts + day5 prereq -> end_of_week fires")
        # Need: 5+ attempts total AND day3 + day5 seen.
        # We have 2 attempts so far. Add 3 more.
        for _ in range(3):
            insert_attempt(pid, all_passed=True)
        # Need to fire day5 first (we already have day3 + day10 seen).
        r = client.get("/api/story/current", headers=auth)
        print(f"  pending after extra attempts: {pending_keys(r.json())}")
        if "act1_day5_ravi_nice_work" not in pending_keys(r.json()):
            print("  --> FAIL: day5 should fire (3+ attempts + day3 seen)"); overall_ok = False
        # Advance day5
        client.post(
            "/api/story/advance",
            headers=auth,
            json={"event_key": "act1_day5_ravi_nice_work", "skipped": False},
        )
        r = client.get("/api/story/current", headers=auth)
        print(f"  pending after day5 advance: {pending_keys(r.json())}")
        if "act1_end_of_week" not in pending_keys(r.json()):
            print("  --> FAIL: end_of_week should be pending now"); overall_ok = False

        section("SUMMARY")
        print(f"  overall_ok = {overall_ok}")

    try:
        os.remove(_DB_PATH)
    except OSError:
        pass
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
