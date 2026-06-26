"""Step 9 verification — progression mechanics (no LLM calls).

Drives the progression helpers directly against the DB so we don't burn
credits. Covers:

  A) update_streak: None -> 1, yesterday -> +1, gap > 1 day -> reset to 1
  B) apply_skill_updates on full pass bumps skill_focus by +0.5 each
  C) apply_skill_updates on fail with primary_gap bumps the gap's skill +0.15
  D) maybe_promote crosses level threshold -> level bump, Ravi message, first_promotion badge
  E) grant_streak_badges -> week_warrior at >=7, unstoppable at >=30
  F) build_player_profile reflects new fields (overall, next_level_title, progress_to_next_level)

Run from project root:
    python -m scripts.test_step9
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

_fd, _DB_PATH = tempfile.mkstemp(prefix="nxtcorp_step9_", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from fastapi.testclient import TestClient  # noqa: E402

from backend.agents.assessor import AssessmentResult  # noqa: E402
from backend.core.question_loader import load_question  # noqa: E402
from backend.db.database import SessionLocal  # noqa: E402
from backend.db.models import ChatMessage, Player, PlayerBadge, SkillScore  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services.profile import build_player_profile  # noqa: E402
from backend.services.run_pipeline import (  # noqa: E402
    apply_skill_updates,
    grant_streak_badges,
    maybe_promote,
    update_streak,
)


def section(t: str) -> None:
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)


def register(client: TestClient, username: str) -> int:
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
    with SessionLocal() as db:
        p = db.query(Player).filter(Player.username == username).one()
        return p.id


def set_all_skills(player_id: int, score: float) -> None:
    with SessionLocal() as db:
        rows = db.query(SkillScore).filter(SkillScore.player_id == player_id).all()
        for r in rows:
            r.score = score
        db.commit()


def get_skill_map(player_id: int) -> dict[str, float]:
    with SessionLocal() as db:
        return {
            r.skill: r.score
            for r in db.query(SkillScore).filter(SkillScore.player_id == player_id).all()
        }


def main() -> int:
    overall_ok = True

    with TestClient(app) as client:
        # Register two distinct players so badge/promo state doesn't bleed.
        player_a_id = register(client, "rookie_a")
        player_b_id = register(client, "rookie_b")
        q = load_question("p001_detect_capital")

        # ===== A) update_streak =====
        section("A) update_streak transitions")
        with SessionLocal() as db:
            p = db.get(Player, player_a_id)
            assert p.last_active_at is None
            update_streak(p, now=datetime(2026, 6, 16, 10, 0))
            print(f"  first call (no prior)        -> streak={p.current_streak}, longest={p.longest_streak}")
            if p.current_streak != 1 or p.longest_streak != 1:
                print("  --> FAIL"); overall_ok = False
            # yesterday -> +1
            p.last_active_at = datetime(2026, 6, 15, 10, 0)
            update_streak(p, now=datetime(2026, 6, 16, 10, 5))
            print(f"  yesterday -> today           -> streak={p.current_streak}, longest={p.longest_streak}")
            if p.current_streak != 2 or p.longest_streak != 2:
                print("  --> FAIL"); overall_ok = False
            # same day -> no change
            update_streak(p, now=datetime(2026, 6, 16, 15, 0))
            print(f"  same day re-call             -> streak={p.current_streak}, longest={p.longest_streak}")
            if p.current_streak != 2:
                print("  --> FAIL"); overall_ok = False
            # 5-day gap -> reset to 1
            p.last_active_at = datetime(2026, 6, 10, 10, 0)
            update_streak(p, now=datetime(2026, 6, 16, 10, 0))
            print(f"  5-day gap                    -> streak={p.current_streak}, longest={p.longest_streak}")
            if p.current_streak != 1 or p.longest_streak != 2:
                print("  --> FAIL"); overall_ok = False
            db.commit()

        # ===== B) apply_skill_updates on pass — catalog-driven =====
        section("B) apply_skill_updates on full pass bumps every skill_focus skill")
        set_all_skills(player_a_id, 1.0)
        focus_skills = list(q.get("skill_focus") or [])
        with SessionLocal() as db:
            p = db.get(Player, player_a_id)
            assessment_pass = AssessmentResult(
                requirement_score=10, output_score=10, overall_score=10,
                primary_gap=None, reasoning="", raw_response="", input_tokens=0, output_tokens=0,
            )
            updates = apply_skill_updates(db, p, q, assessment_pass.primary_gap, all_passed=True)
            db.commit()
        print(f"  skill_focus = {focus_skills}")
        print(f"  updates: {[(u.skill, u.delta, u.new_score) for u in updates]}")
        skills = get_skill_map(player_a_id)
        for s in focus_skills:
            if abs(skills[s] - 1.5) > 0.01:
                print(f"  --> FAIL: {s} should be 1.5 (was 1.0 + 0.5 focus bump)"); overall_ok = False
        # Skills NOT in focus must stay at 1.0.
        all_skills = {"decomposition", "edge_case", "requirement_completeness", "output_verification", "iterative_refinement"}
        for s in all_skills - set(focus_skills):
            if abs(skills[s] - 1.0) > 0.01:
                print(f"  --> FAIL: {s} not in focus, shouldn't move"); overall_ok = False

        # ===== C) apply_skill_updates on failure with primary_gap — catalog-driven =====
        section("C) apply_skill_updates on fail with primary_gap bumps that gap's skill")
        # Pick the first gap from the taxonomy + the skill it points at.
        gap = (q.get("gap_taxonomy") or [None])[0]
        if gap is None:
            print("  --> SKIP: question has no gap_taxonomy")
        else:
            target_gap_key = gap["key"]
            target_skill = gap["skill"]
            set_all_skills(player_a_id, 2.0)
            with SessionLocal() as db:
                p = db.get(Player, player_a_id)
                assessment_fail = AssessmentResult(
                    requirement_score=5, output_score=7.5, overall_score=6,
                    primary_gap=target_gap_key,
                    reasoning="", raw_response="", input_tokens=0, output_tokens=0,
                )
                updates = apply_skill_updates(db, p, q, assessment_fail.primary_gap, all_passed=False)
                db.commit()
            print(f"  primary_gap={target_gap_key!r}  -> skill={target_skill!r}")
            print(f"  updates: {[(u.skill, u.delta, u.new_score) for u in updates]}")
            skills = get_skill_map(player_a_id)
            if abs(skills[target_skill] - 2.15) > 0.01:
                print(f"  --> FAIL: {target_skill} should be 2.15 (was 2.0 + 0.15 gap learning bump), got {skills[target_skill]}")
                overall_ok = False
            other = next((s for s in {"decomposition", "edge_case", "requirement_completeness", "output_verification", "iterative_refinement"} if s != target_skill), None)
            if other and abs(skills[other] - 2.0) > 0.01:
                print(f"  --> FAIL: {other} shouldn't move when gap targets {target_skill}"); overall_ok = False

        # ===== D) maybe_promote across threshold =====
        section("D) maybe_promote when overall crosses 3.0 -> level 2")
        set_all_skills(player_b_id, 3.2)  # overall = 3.2 -> level 2
        with SessionLocal() as db:
            p = db.get(Player, player_b_id)
            assert p.job_level == 1
            new_level, promo_badges = maybe_promote(db, p, "p001_detect_capital", related_attempt_id=None)
            db.commit()
        print(f"  new_level={new_level}  promo_badges={promo_badges}")
        if new_level != 2:
            print(f"  --> FAIL: expected level 2, got {new_level}"); overall_ok = False
        if "first_promotion" not in promo_badges:
            print(f"  --> FAIL: first_promotion badge not granted"); overall_ok = False
        # Ravi message persisted?
        with SessionLocal() as db:
            msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.player_id == player_b_id, ChatMessage.character == "ravi")
                .all()
            )
            print(f"  ravi messages: {len(msgs)}")
            if not msgs:
                print("  --> FAIL: no Ravi promotion ChatMessage"); overall_ok = False
            else:
                print(f"    body: {msgs[0].body[:100]}…")
                if "AI Power User" not in msgs[0].body:
                    print("  --> FAIL: Ravi message doesn't mention the new title"); overall_ok = False
            # first_promotion badge in DB?
            badge = (
                db.query(PlayerBadge)
                .filter(PlayerBadge.player_id == player_b_id, PlayerBadge.badge_key == "first_promotion")
                .first()
            )
            if badge is None:
                print("  --> FAIL: first_promotion badge missing in DB"); overall_ok = False

        # Second call shouldn't re-promote.
        section("D2) maybe_promote second call doesn't re-fire at same level")
        with SessionLocal() as db:
            p = db.get(Player, player_b_id)
            new_level, promo_badges = maybe_promote(db, p, "p001_detect_capital", related_attempt_id=None)
        print(f"  new_level={new_level}  promo_badges={promo_badges}")
        if new_level is not None or promo_badges:
            print("  --> FAIL: shouldn't re-promote when at the same level"); overall_ok = False

        # ===== E) grant_streak_badges =====
        section("E) grant_streak_badges at streak thresholds")
        with SessionLocal() as db:
            p = db.get(Player, player_a_id)
            p.current_streak = 7
            db.commit()
            earned7 = grant_streak_badges(db, p)
            db.commit()
        print(f"  streak=7 -> earned: {earned7}")
        if "week_warrior" not in earned7:
            print("  --> FAIL: week_warrior not granted at streak 7"); overall_ok = False

        with SessionLocal() as db:
            p = db.get(Player, player_a_id)
            p.current_streak = 30
            db.commit()
            earned30 = grant_streak_badges(db, p)
            db.commit()
        print(f"  streak=30 -> earned: {earned30}")
        if "unstoppable" not in earned30:
            print("  --> FAIL: unstoppable not granted at streak 30"); overall_ok = False
        if "week_warrior" in earned30:
            print("  --> FAIL: week_warrior should only grant once"); overall_ok = False

        # ===== F) build_player_profile reflects new fields =====
        section("F) build_player_profile shape")
        set_all_skills(player_b_id, 5.5)  # should still be level 2 (next threshold 5.0 already crossed by maybe_promote earlier? player_b is at level 2 from D)
        with SessionLocal() as db:
            p = db.get(Player, player_b_id)
            # Re-promote since overall now 5.5 (>= 5.0 threshold = level 3)
            maybe_promote(db, p, "p001_detect_capital", related_attempt_id=None)
            db.commit()
            prof = build_player_profile(db, p)
        print(f"  job_level={prof.job_level}  job_title={prof.job_title}")
        print(f"  next_level_title={prof.next_level_title}")
        print(f"  overall_skill_score={prof.overall_skill_score}")
        print(f"  progress_to_next_level={prof.progress_to_next_level}")
        if prof.job_level != 3 or prof.job_title != "AI Power User":
            print("  --> FAIL: should be level 3"); overall_ok = False
        if prof.next_level_title != "AI Work Specialist":
            print("  --> FAIL: next_level_title should be 'AI Work Specialist'"); overall_ok = False
        if abs(prof.overall_skill_score - 5.5) > 0.01:
            print("  --> FAIL: overall_skill_score should be 5.5"); overall_ok = False
        # Level 3 spans 5.0..7.0. Overall 5.5 -> progress 0.25.
        if abs(prof.progress_to_next_level - 0.25) > 0.01:
            print(f"  --> FAIL: progress_to_next_level should be 0.25, got {prof.progress_to_next_level}")
            overall_ok = False

        section("SUMMARY")
        print(f"  overall_ok = {overall_ok}")

    try:
        os.remove(_DB_PATH)
    except OSError:
        pass
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
