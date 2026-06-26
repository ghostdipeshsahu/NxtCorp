from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------- Skills & badges ----------

SkillKey = Literal[
    "decomposition",
    "edge_case",
    "requirement_completeness",
    "output_verification",
    "iterative_refinement",
    "prompt_optimization",
]

SKILL_KEYS: tuple[SkillKey, ...] = (
    "decomposition",
    "edge_case",
    "requirement_completeness",
    "output_verification",
    "iterative_refinement",
    "prompt_optimization",  # PHASE 4 HOOK — Prompt Optimization (Skill 6) — not yet active
)

JOB_LEVELS = {
    1: "AI Trainee",
    2: "AI Professional",
    3: "AI Power User",
    4: "AI Work Specialist",
    5: "AI Work Expert",
}

CharacterKey = Literal["priya", "arjun", "zara", "ravi", "player"]
Expression = Literal["happy", "thinking", "concerned", "excited", "neutral", "proud"]
ExerciseType = Literal[1, 2, 3, 4, 5]

# v3: job role chosen at onboarding. Drives task personalization in the
# Client Task Agent (e.g. data_analyst sees dataframe-flavored tasks).
JobRole = Literal[
    "software_developer",
    "data_analyst",
    "genai_engineer",
    "qa_engineer",
    "devops_engineer",
]

JOB_ROLES: tuple[JobRole, ...] = (
    "software_developer",
    "data_analyst",
    "genai_engineer",
    "qa_engineer",
    "devops_engineer",
)

JOB_ROLE_LABELS: dict[str, str] = {
    "software_developer": "Software Developer",
    "data_analyst":       "Data Analyst",
    "genai_engineer":     "GenAI Engineer",
    "qa_engineer":        "QA Engineer",
    "devops_engineer":    "DevOps Engineer",
}


# ---------- Auth ----------

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)
    avatar_id: str = Field(default="avatar_01", max_length=32)
    pronouns: Optional[str] = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    username: str
    password: str


class OnboardingCompleteRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=64)
    avatar_id: str = Field(min_length=1, max_length=32)
    pronouns: Optional[str] = Field(default=None, max_length=32)
    job_role: JobRole = "software_developer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Player ----------

class SkillScoreOut(BaseModel):
    skill: SkillKey
    score: float
    tier: str  # 🌱 Beginner | ⚡ Developing | 🔥 Proficient | 💎 Expert


class BadgeOut(BaseModel):
    badge_key: str
    earned_at: datetime


class PlayerProfile(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_id: str
    pronouns: Optional[str]
    job_role: JobRole = "software_developer"
    job_role_label: str = "Software Developer"
    job_level: int
    job_title: str
    next_level_title: Optional[str] = None
    progress_to_next_level: float = 0.0   # 0..1, based on overall skill score
    overall_skill_score: float = 0.0      # 0..10, mean of the five skills
    total_xp: int
    xp_to_next_level: int
    current_streak: int
    longest_streak: int
    story_act: int
    story_day: int
    onboarding_done: bool
    progression_phase: str = "1"   # v3: "0" | "1" | "2a" | "2b" | "3" | "4"
    skills: list[SkillScoreOut]
    badges: list[BadgeOut]


# ---------- Story ----------

class StoryMessage(BaseModel):
    character: CharacterKey
    expression: Expression
    body: str


class StoryEvent(BaseModel):
    event_key: str
    title: str
    messages: list[StoryMessage]
    xp_bonus: int = 0
    story_day: Optional[int] = None
    story_act: Optional[int] = None


class StoryState(BaseModel):
    act: int
    day: int
    pending_events: list[StoryEvent]


class StoryAdvanceRequest(BaseModel):
    event_key: str = Field(min_length=1, max_length=64)
    skipped: bool = False


class StoryAdvanceResponse(BaseModel):
    event_key: str
    xp_awarded: int
    story_day: int
    story_act: int


# ---------- Tasks / exercises ----------

class SampleTest(BaseModel):
    input: Any
    expected: Any
    description: Optional[str] = None


class ExpectedSubtask(BaseModel):
    key: str
    description: str


class ExpectedGap(BaseModel):
    key: str
    description: str


class StudentTestCase(BaseModel):
    input: Any
    expected: Any


class TaskView(BaseModel):
    question_id: str
    exercise_type: ExerciseType
    title: str
    framing_character: CharacterKey
    # Center-panel quote block (ticket-context framing, business-flavored).
    framing_message: str
    # Right-panel team-chat Priya line (her voice, not the ticket text).
    # Falls back to None when the question doesn't define one; frontend
    # substitutes a generic Priya voice line — NOT the framing_message.
    priya_chat_message: Optional[str] = None
    # v4: Meeting Room playback script. Each entry is one team member
    # speaking during the pre-task briefing. Empty list = question has
    # no script yet; frontend shows a placeholder + skip to desk.
    meeting_script: list[dict[str, Any]] = []
    # v5: true when this player has already finished the meeting for this
    # question. Frontend hides the "Join Meeting →" CTA after this flips,
    # so Priya's later coaching messages no longer re-trigger the meeting.
    meeting_completed: bool = False
    problem_description: str
    sample_tests: list[SampleTest]
    function_signature: Optional[str] = None
    notes: Optional[str] = None
    # Type-specific extras — only populated for the relevant exercise type:
    flawed_prompt: Optional[str] = None         # Type 2 — Spot the Gap
    target_code: Optional[str] = None           # Type 4 — Verify
    failing_prompt: Optional[str] = None        # Type 5 — Diagnose and Fix
    failing_inputs_hint: Optional[list[Any]] = None  # Type 5 — which sample inputs failed
    expected_subtasks_count: Optional[int] = None    # Type 1 — hint to player about list length
    expected_gaps_count: Optional[int] = None        # Type 2 — hint


class RunRequest(BaseModel):
    """Single endpoint, polymorphic body. Only the field for the active
    exercise type is required; the others are unused.
    """
    attempt_number: int = Field(ge=1)
    # Type 3 + Type 5
    student_prompt: Optional[str] = Field(default=None, max_length=8000)
    # Type 1
    subtasks: Optional[list[str]] = None
    # Type 2
    identified_gaps: Optional[list[str]] = None
    # Type 4
    test_cases: Optional[list[StudentTestCase]] = None


class TestCaseResult(BaseModel):
    input: Any
    expected: Any
    actual: Any
    passed: bool
    error: Optional[str] = None


class CoachMessage(BaseModel):
    character: CharacterKey
    expression: Expression
    body: str
    escalation_level: int  # 1..4


class SkillDelta(BaseModel):
    skill: SkillKey
    delta: float
    new_score: float


class RunResponse(BaseModel):
    attempt_id: int
    test_results: list[TestCaseResult]
    sample_passed: int
    sample_total: int
    hidden_passed: int
    hidden_total: int
    all_passed: bool
    xp_earned: int
    badges_earned: list[str]
    skill_updates: list[SkillDelta]
    coach_message: CoachMessage
    primary_gap: Optional[str] = None
    # v3: true when Arjun helped on this task at any point; UI shows
    # "40 XP — Arjun helped out on this one" when both this and all_passed are true.
    arjun_triggered: bool = False
    # v3: when this attempt won the Employee of the Month award for the
    # current calendar month, this carries the year_month string ("YYYY-MM").
    # Drives the frontend cinematic. None otherwise.
    employee_of_month_awarded: Optional[str] = None
    # v5: PUBLIC-SAFE Zara assessment payload for the center-panel card.
    # Contains scores + flags + status_message ONLY. Never primary_gap,
    # zara_note, gaps_covered, or gaps_missing — those stay internal so
    # Priya can coach without leaking the answer. See run_pipeline._build_public_zara_payload.
    zara_assessment: Optional[dict[str, Any]] = None


class RespondRequest(BaseModel):
    student_response: str = Field(min_length=1, max_length=4000)


class RespondResponse(BaseModel):
    coach_followup: CoachMessage


class HintResponse(BaseModel):
    hint_message: str
    xp_deducted: int
    xp_remaining: int
