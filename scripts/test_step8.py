"""Step 8 verification — exercise the onboarding endpoint via FastAPI TestClient.

No LLM calls. Just:
  1. Register a new player (onboarding_done starts False).
  2. POST /api/onboarding/complete with name + avatar + pronouns.
  3. Assert profile reflects the new values, onboarding_done becomes True.
  4. Second POST returns 409.
  5. PlayerStoryEvent rows for day1_priya_welcome + day1_arjun_intro are recorded.

Run from project root:
    python -m scripts.test_step8
"""

from __future__ import annotations

import os
import sys
import tempfile

_fd, _DB_PATH = tempfile.mkstemp(prefix="nxtcorp_step8_", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from fastapi.testclient import TestClient  # noqa: E402

from backend.db.database import SessionLocal  # noqa: E402
from backend.db.models import PlayerStoryEvent  # noqa: E402
from backend.main import app  # noqa: E402


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    overall_ok = True

    with TestClient(app) as client:
        section("1) Register fresh player")
        r = client.post(
            "/api/auth/register",
            json={
                "username": "rookie_step8",
                "password": "hunter2hunter2",
                "display_name": "rookie_step8",
                "avatar_id": "avatar_02",
            },
        )
        print(f"  status: {r.status_code}")
        if r.status_code != 201:
            print(f"  body: {r.text}"); return 1
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        section("2) Profile says onboarding_done=False right after register")
        r = client.get("/api/player/profile", headers=auth)
        prof = r.json()
        print(f"  display_name: {prof['display_name']}  onboarding_done: {prof['onboarding_done']}")
        if prof["onboarding_done"] is not False:
            print("  --> FAIL: should be False on fresh register"); overall_ok = False

        section("3) POST /api/onboarding/complete")
        r = client.post(
            "/api/onboarding/complete",
            headers=auth,
            json={
                "display_name": "Aarav",
                "avatar_id": "avatar_04",
                "pronouns": "he/him",
            },
        )
        print(f"  status: {r.status_code}")
        if r.status_code != 200:
            print(f"  body: {r.text}"); return 1
        out = r.json()
        print(f"  display_name: {out['display_name']!r}  avatar_id: {out['avatar_id']!r}  "
              f"pronouns: {out['pronouns']!r}  onboarding_done: {out['onboarding_done']}")

        if out["display_name"] != "Aarav":
            print("  --> FAIL: display_name not updated"); overall_ok = False
        if out["avatar_id"] != "avatar_04":
            print("  --> FAIL: avatar_id not updated"); overall_ok = False
        if out["pronouns"] != "he/him":
            print("  --> FAIL: pronouns not stored"); overall_ok = False
        if out["onboarding_done"] is not True:
            print("  --> FAIL: onboarding_done should be True"); overall_ok = False

        section("4) Story events recorded in DB")
        with SessionLocal() as db:
            keys = {
                e.event_key
                for e in db.query(PlayerStoryEvent)
                .filter(PlayerStoryEvent.player_id == out["id"])
                .all()
            }
        print(f"  recorded events: {sorted(keys)}")
        for required in ("day1_priya_welcome", "day1_arjun_intro"):
            if required not in keys:
                print(f"  --> FAIL: missing event {required!r}"); overall_ok = False

        section("5) Second POST returns 409 (idempotency guard)")
        r = client.post(
            "/api/onboarding/complete",
            headers=auth,
            json={"display_name": "Different", "avatar_id": "avatar_01"},
        )
        print(f"  status: {r.status_code}")
        if r.status_code != 409:
            print("  --> FAIL: expected 409"); overall_ok = False

        section("SUMMARY")
        print(f"  overall_ok = {overall_ok}")

    try:
        os.remove(_DB_PATH)
    except OSError:
        pass
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
