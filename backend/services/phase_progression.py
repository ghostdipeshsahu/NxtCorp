"""
Phase progression (v3 — Change 12).

The student moves through six learning phases:

  Phase 0   — Onboarding micro-tasks. AI-supervision concepts introduced
              with tiny problems that take one attempt to finish. The point
              is to teach the GAME, not test skill.
  Phase 1   — Foundational AI-supervision practice. Five skills exercised
              one at a time (one exercise type per task) on simple problems.
              This is where most beginners spend the bulk of their time.
  Phase 2a  — Skill stress. The student's weakest skill from Phase 1 is
              targeted with tasks designed to expose that gap.
  Phase 2b  — Integration. Combined exercises that exercise two or three
              skills simultaneously on slightly larger problems.
  Phase 3   — Advanced. Multi-stage tasks where decomposition + edge case
              thinking + verification all matter on the same problem.
  Phase 4   — Prompt Optimization. Locked until Phase 3 mastery. This is
              where the 6th skill (prompt_optimization) is exercised.

Each question carries a `phase` field (default "1"). This module:
  - picks the next question filtered to the player's current phase,
  - auto-advances the player to the next phase when their overall skill
    crosses a phase-specific threshold, AND they've completed at least
    one question in the current phase,
  - exposes phase-aware scoring multipliers so XP and skill bumps can
    reflect difficulty.

The thresholds are tunable — see PHASE_ORDER and PHASE_THRESHOLDS.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.core.question_loader import load_question
from backend.db.models import Player, PlayerCompletedTask, SkillScore
from backend.services.profile import compute_overall_skill
from backend.services.question_progression import (
    completed_ids_for,
    list_question_ids,
)


# Canonical phase ordering. "4" is the locked Prompt Optimization phase —
# the runtime can advance into it but no questions exist yet.
PHASE_ORDER: tuple[str, ...] = ("0", "1", "2a", "2b", "3", "4")

# Minimum overall_skill_score to advance INTO each phase.
# Phase 0 is the entry phase; everyone starts there (or in 1 if onboarding-done).
PHASE_THRESHOLDS: dict[str, float] = {
    "0":  0.0,
    "1":  0.0,
    "2a": 3.0,
    "2b": 4.5,
    "3":  6.5,
    "4":  9.0,
}

# Phase-aware XP multipliers. Earlier phases pay less per task because the
# problems are easier; advanced phases pay more.
PHASE_XP_MULTIPLIER: dict[str, float] = {
    "0":  0.5,
    "1":  1.0,
    "2a": 1.15,
    "2b": 1.25,
    "3":  1.5,
    "4":  1.75,
}

# Minimum number of completed tasks in the current phase before the
# player is eligible to advance to the next phase.
MIN_TASKS_PER_PHASE: int = 2


def _phase_of_question(question_id: str) -> str:
    """Read the `phase` field from a question file. Defaults to "1" for
    legacy questions that pre-date phases.
    """
    try:
        q = load_question(question_id)
    except Exception:
        return "1"
    raw = q.get("phase")
    if isinstance(raw, (int, float)):
        raw = str(raw)
    if not isinstance(raw, str):
        return "1"
    raw = raw.strip().lower()
    return raw if raw in PHASE_ORDER else "1"


def _completed_count_in_phase(db: Session, player: Player, phase: str) -> int:
    rows = (
        db.query(PlayerCompletedTask)
        .filter(PlayerCompletedTask.player_id == player.id)
        .all()
    )
    return sum(1 for r in rows if _phase_of_question(r.question_id) == phase)


def current_phase_of(player: Player) -> str:
    """Read-only accessor — returns the player's current phase (with safe default)."""
    val = getattr(player, "progression_phase", None) or "1"
    return val if val in PHASE_ORDER else "1"


def question_ids_in_phase(phase: str) -> list[str]:
    """All catalog question IDs whose `phase` matches the requested phase,
    in canonical order.
    """
    return [qid for qid in list_question_ids() if _phase_of_question(qid) == phase]


def next_question_for_phase(
    db: Session,
    player: Player,
) -> Optional[str]:
    """First un-completed question in the player's current phase. None if
    the player has cleared every question in this phase.
    """
    done = completed_ids_for(db, player)
    for qid in question_ids_in_phase(current_phase_of(player)):
        if qid not in done:
            return qid
    return None


def maybe_advance_phase(db: Session, player: Player) -> Optional[str]:
    """If the player meets the thresholds AND has cleared at least
    MIN_TASKS_PER_PHASE in their current phase, advance them to the next
    phase. Returns the new phase if advanced, else None.

    Caller is responsible for db.commit().
    """
    current = current_phase_of(player)
    idx = PHASE_ORDER.index(current) if current in PHASE_ORDER else 1
    if idx >= len(PHASE_ORDER) - 1:
        return None
    next_phase = PHASE_ORDER[idx + 1]

    # Threshold check — based on overall skill score.
    skills = (
        db.query(SkillScore)
        .filter(SkillScore.player_id == player.id)
        .all()
    )
    overall = compute_overall_skill(skills)
    if overall < PHASE_THRESHOLDS.get(next_phase, 0.0):
        return None

    # Volume check — must have actually practiced this phase.
    if _completed_count_in_phase(db, player, current) < MIN_TASKS_PER_PHASE:
        return None

    player.progression_phase = next_phase
    return next_phase


def phase_xp_multiplier(player: Player) -> float:
    return PHASE_XP_MULTIPLIER.get(current_phase_of(player), 1.0)


__all__ = [
    "PHASE_ORDER",
    "PHASE_THRESHOLDS",
    "PHASE_XP_MULTIPLIER",
    "current_phase_of",
    "maybe_advance_phase",
    "next_question_for_phase",
    "phase_xp_multiplier",
    "question_ids_in_phase",
]
