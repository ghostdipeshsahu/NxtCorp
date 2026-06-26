"""One-shot DB reset for the v4 curriculum switch.

The 15 legacy question files (p001_detect_capital … p015_bmi_category) have
been replaced by 5 new Phase-1 tasks (p001_bonus_calculator … p005_grade_calculator).
The schema, IDs, and gap structures all changed. Existing rows referring to
old IDs would either crash the runtime or surface stale completions.

This script:
  - Deletes every PlayerCompletedTask row (all players start fresh on p001).
  - Deletes every Attempt row (those reference question_ids that no longer
    exist, and many use old field shapes).
  - Deletes every ChatMessage tied to those attempts (orphaned otherwise).
  - Deletes every PlayerStoryEvent (story rails will replay cleanly).
  - Resets every player's progression_phase to "1".
  - Resets every player's job_level back to 1 (so they re-earn promotions).
  - Resets every player's XP + streak counters.
  - Wipes every SkillScore back to 0.

Does NOT touch:
  - Player accounts (username, password_hash, display_name, avatar_id, job_role)
  - EmployeeOfMonth history (historical record stays)
  - PlayerBadge history

Run once, after deploying the new question files:
    python -m scripts.reset_progress
"""

from __future__ import annotations

import sys

from sqlalchemy import delete, update

from backend.db.database import SessionLocal, init_db
from backend.db.models import (
    Attempt,
    ChatMessage,
    Player,
    PlayerCompletedTask,
    PlayerStoryEvent,
    SkillScore,
)


def main() -> int:
    init_db()  # ensure tables exist before we touch them
    with SessionLocal() as db:
        n_completed = db.execute(delete(PlayerCompletedTask)).rowcount
        n_attempts = db.execute(delete(Attempt)).rowcount
        n_messages = db.execute(delete(ChatMessage)).rowcount
        n_story = db.execute(delete(PlayerStoryEvent)).rowcount

        # Reset per-player progression counters in one update.
        n_players = db.execute(
            update(Player).values(
                progression_phase="1",
                job_level=1,
                total_xp=0,
                current_streak=0,
                longest_streak=0,
                last_active_at=None,
            )
        ).rowcount

        # Wipe skill scores back to 0 (rows stay — runtime expects one per
        # (player, skill) pair). Done as an UPDATE instead of DELETE so the
        # backfill in init_db doesn't have to rerun.
        n_skills = db.execute(update(SkillScore).values(score=0.0)).rowcount

        db.commit()

    print("== v4 progress reset ==")
    print(f"  completed_tasks deleted:   {n_completed}")
    print(f"  attempts deleted:          {n_attempts}")
    print(f"  chat_messages deleted:     {n_messages}")
    print(f"  player_story_events:       {n_story}")
    print(f"  players reset (XP/level):  {n_players}")
    print(f"  skill_scores reset to 0:   {n_skills}")
    print()
    print("Every student will now open in Phase 1 at p001_bonus_calculator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
