"""Build a PlayerProfile response shape from DB state.

Centralized so the auth/profile/onboarding/run endpoints all return the same
calculated fields — overall skill, level title, progress to next level, etc.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.progression import (
    job_title,
    next_level_title,
    progress_to_next_level,
    skill_tier,
    xp_to_next_level,
)
from backend.db.models import Player, PlayerBadge, SkillScore
from backend.models.schemas import (
    JOB_ROLE_LABELS,
    BadgeOut,
    PlayerProfile,
    SkillScoreOut,
)


def compute_overall_skill(skills: list[SkillScore]) -> float:
    if not skills:
        return 0.0
    return sum(s.score for s in skills) / len(skills)


def build_player_profile(db: Session, player: Player) -> PlayerProfile:
    skills = (
        db.query(SkillScore)
        .filter(SkillScore.player_id == player.id)
        .order_by(SkillScore.skill.asc())
        .all()
    )
    badges = (
        db.query(PlayerBadge)
        .filter(PlayerBadge.player_id == player.id)
        .order_by(PlayerBadge.earned_at.asc())
        .all()
    )
    overall = round(compute_overall_skill(skills), 2)

    job_role = getattr(player, "job_role", "software_developer") or "software_developer"
    return PlayerProfile(
        id=player.id,
        username=player.username,
        display_name=player.display_name,
        avatar_id=player.avatar_id,
        pronouns=player.pronouns,
        job_role=job_role,  # type: ignore[arg-type]
        job_role_label=JOB_ROLE_LABELS.get(job_role, "Software Developer"),
        job_level=player.job_level,
        job_title=job_title(player.job_level),
        next_level_title=next_level_title(player.job_level),
        progress_to_next_level=round(progress_to_next_level(overall, player.job_level), 4),
        overall_skill_score=overall,
        total_xp=player.total_xp,
        xp_to_next_level=xp_to_next_level(player.total_xp, player.job_level),
        current_streak=player.current_streak,
        longest_streak=player.longest_streak,
        story_act=player.story_act,
        story_day=player.story_day,
        onboarding_done=player.onboarding_done,
        progression_phase=getattr(player, "progression_phase", "1") or "1",
        skills=[
            SkillScoreOut(skill=s.skill, score=round(s.score, 2), tier=skill_tier(s.score))  # type: ignore[arg-type]
            for s in skills
        ],
        badges=[BadgeOut(badge_key=b.badge_key, earned_at=b.earned_at) for b in badges],
    )


__all__ = ["build_player_profile", "compute_overall_skill"]
