from __future__ import annotations

from typing import Optional

from backend.models.schemas import JOB_LEVELS


def skill_tier(score: float) -> str:
    if score < 3:
        return "🌱 Beginner"
    if score < 6:
        return "⚡ Developing"
    if score < 8:
        return "🔥 Proficient"
    return "💎 Expert"


def job_title(level: int) -> str:
    return JOB_LEVELS.get(level, "AI Trainee")


# Overall-skill thresholds drive promotions (spec §7).
# Level 1: 0-3, 2: 3-5, 3: 5-7, 4: 7-9, 5: 9-10
LEVEL_THRESHOLDS = [0.0, 3.0, 5.0, 7.0, 9.0]
LEVEL_CAP_SCORE = 10.0


def level_for_overall(overall: float) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS, start=1):
        if overall >= threshold:
            level = i
    return level


def next_level_title(current_level: int) -> Optional[str]:
    nxt = current_level + 1
    if nxt > max(JOB_LEVELS.keys()):
        return None
    return JOB_LEVELS[nxt]


def progress_to_next_level(overall: float, current_level: int) -> float:
    """Fraction (0..1) of the way from the current level threshold to the next."""
    if current_level >= max(JOB_LEVELS.keys()):
        return 1.0
    floor = LEVEL_THRESHOLDS[current_level - 1]
    ceiling = (
        LEVEL_THRESHOLDS[current_level]
        if current_level < len(LEVEL_THRESHOLDS)
        else LEVEL_CAP_SCORE
    )
    span = max(1e-6, ceiling - floor)
    return max(0.0, min(1.0, (overall - floor) / span))


# XP curve placeholder — total XP needed to reach the start of each level.
# Used only for the TopBar's "X / Y XP" estimate; level transitions are
# triggered by overall skill score, not XP.
XP_PER_LEVEL = [0, 500, 1500, 3500, 7000, 15000]


def xp_to_next_level(current_xp: int, current_level: int) -> int:
    next_level = min(current_level + 1, len(XP_PER_LEVEL) - 1)
    target = XP_PER_LEVEL[next_level]
    return max(0, target - current_xp)
