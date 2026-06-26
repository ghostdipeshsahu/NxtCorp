from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


def _now() -> datetime:
    return datetime.utcnow()


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar_id: Mapped[str] = mapped_column(String(32), nullable=False, default="avatar_01")
    pronouns: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # v3: job role chosen during onboarding. Personalizes the Client Task
    # Agent's task framing. One of: software_developer, data_analyst,
    # genai_engineer, qa_engineer, devops_engineer.
    job_role: Mapped[str] = mapped_column(String(32), nullable=False, default="software_developer")

    job_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    story_act: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    story_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # v3: phase progression. Values: "0", "1", "2a", "2b", "3", "4".
    # Stored as VARCHAR because of the "2a" / "2b" sub-phases. Default "1"
    # so newly registered players go straight into Phase 1.
    progression_phase: Mapped[str] = mapped_column(String(8), nullable=False, default="1")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    skills = relationship("SkillScore", back_populates="player", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="player", cascade="all, delete-orphan")
    badges = relationship("PlayerBadge", back_populates="player", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="player", cascade="all, delete-orphan")
    story_events = relationship("PlayerStoryEvent", back_populates="player", cascade="all, delete-orphan")
    completed_tasks = relationship(
        "PlayerCompletedTask", back_populates="player", cascade="all, delete-orphan",
    )


class SkillScore(Base):
    __tablename__ = "skill_scores"
    __table_args__ = (UniqueConstraint("player_id", "skill", name="uq_player_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(48), nullable=False)  # decomposition | edge_case | requirement_completeness | output_verification | iterative_refinement
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now, onupdate=_now)

    player = relationship("Player", back_populates="skills")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    exercise_type: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    student_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    generated_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    requirement_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    output_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    primary_gap: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    all_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # v3: True when Arjun helped on this task at any prior attempt OR on this
    # one. Drives the UI note ("40 XP — Arjun helped out on this one") and the
    # XP cap. Mirrors the in-pipeline `arjun_helped` flag.
    arjun_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    player = relationship("Player", back_populates="attempts")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    character: Mapped[str] = mapped_column(String(32), nullable=False)  # priya | arjun | zara | ravi | player
    expression: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_question_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    related_attempt_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    player = relationship("Player", back_populates="messages")


class PlayerBadge(Base):
    __tablename__ = "player_badges"
    __table_args__ = (UniqueConstraint("player_id", "badge_key", name="uq_player_badge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    badge_key: Mapped[str] = mapped_column(String(64), nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    player = relationship("Player", back_populates="badges")


class PlayerStoryEvent(Base):
    __tablename__ = "player_story_events"
    __table_args__ = (UniqueConstraint("player_id", "event_key", name="uq_player_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    player = relationship("Player", back_populates="story_events")


class EmployeeOfMonth(Base):
    """v3: monthly EotM award. One row per (player, year_month). Carries the
    snapshot of the 5 criteria so we can show the cinematic with real numbers
    and so a re-run of the awarder is idempotent for that month.
    """

    __tablename__ = "employee_of_month"
    __table_args__ = (
        UniqueConstraint("player_id", "year_month", name="uq_eom_player_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # "YYYY-MM"

    tasks_completed:  Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_try_count:  Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clean_passes:     Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak:   Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_l4_reveals:    Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    xp_awarded:   Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    awarded_at:   Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class PlayerMeetingCompletion(Base):
    """v5: one row per (player, question_id) once the student has finished
    the Meeting Room briefing for that task. Persists across refreshes so
    the cabin → meeting flow never replays for the same ticket. Used by
    the task route to populate TaskView.meeting_completed.
    """

    __tablename__ = "player_meeting_completion"
    __table_args__ = (
        UniqueConstraint("player_id", "question_id", name="uq_player_meeting_completion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class PlayerCompletedTask(Base):
    """One row per (player, question_id) when the player passes every test.

    Used by the progression service to pick the next question. The first
    pass is the canonical completion — re-passing a question doesn't move
    the player forward, but `attempts_taken` tracks how many tries it took.
    """

    __tablename__ = "player_completed_tasks"
    __table_args__ = (
        UniqueConstraint("player_id", "question_id", name="uq_player_completed_task"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempts_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    player = relationship("Player", back_populates="completed_tasks")
