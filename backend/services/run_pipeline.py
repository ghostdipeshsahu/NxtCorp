"""
Run pipeline (step 6, extended steps 9 + types).

Single orchestrator. Reads `exercise_type` from the question file and
dispatches to the matching per-type runner:

  Type 1 — Decompose         -> LLM judge over expected_subtasks
  Type 2 — Spot the Gap       -> LLM judge over expected_gaps
  Type 3 — Specify and Execute -> code_generator + executor + assessor
  Type 4 — Verify             -> deterministic match of student's test cases
                                 against the gap_taxonomy via reference_code
  Type 5 — Diagnose and Fix   -> like Type 3, but the question carries the
                                 prior failing_prompt as context

All five types share the bottom-of-pipeline mechanics (Attempt row,
chat messages, skill updates, level promotion, badges, RunResponse).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.agents.assessor import AssessmentResult, assess
from backend.agents.coach import coach, coach_arjun_greeting, compute_step
from backend.agents.judge import CoverageResult, judge_coverage
from backend.core.code_executor import ExecutionResult, TestOutcome, execute
from backend.core.code_generator import generate_code
from backend.core.progression import (
    job_title,
    level_for_overall,
)
from backend.core.question_loader import (
    function_name_from_signature,
    load_question,
)
from backend.db.models import (
    Attempt,
    ChatMessage,
    EmployeeOfMonth,
    Player,
    PlayerBadge,
    PlayerCompletedTask,
    SkillScore,
)
from backend.models.schemas import (
    CoachMessage,
    RunResponse,
    SkillDelta,
    TestCaseResult,
)
from backend.services.phase_progression import (
    maybe_advance_phase,
    phase_xp_multiplier,
)
from backend.services.profile import compute_overall_skill
from backend.services.question_progression import mark_completed


# ---------- XP curve (spec §7) ----------

FIRST_TRY_PASS_XP = 150
FIRST_TRY_BONUS_XP = 50
SECOND_TRY_PASS_XP = 80
THIRD_OR_LATER_PASS_XP = 40
FAIL_CONSOLATION_XP = 10
STREAK_BONUS_RATE = 0.10
# v3: when Arjun helped on this task at any point, the per-task XP is
# capped at this value regardless of streak / first-try math.
ARJUN_HELP_XP_CAP = 40


def compute_xp_base(all_passed: bool, attempt_number: int) -> tuple[int, list[str]]:
    badges: list[str] = []
    if not all_passed:
        return FAIL_CONSOLATION_XP, badges
    if attempt_number == 1:
        badges.append("first_try")
        return FIRST_TRY_PASS_XP + FIRST_TRY_BONUS_XP, badges
    if attempt_number == 2:
        return SECOND_TRY_PASS_XP, badges
    return THIRD_OR_LATER_PASS_XP, badges


# ---------- Skill updates ----------

PASS_FOCUS_SKILL_BUMP = 0.5
FAIL_GAP_SKILL_BUMP = 0.15
SKILL_CAP = 10.0
SKILL_FLOOR = 0.0


def _bump_skill(score: float, delta: float) -> float:
    return max(SKILL_FLOOR, min(SKILL_CAP, score + delta))


def apply_skill_updates(
    db: Session,
    player: Player,
    question: dict[str, Any],
    primary_gap: Optional[str],
    all_passed: bool,
) -> list[SkillDelta]:
    skills_by_key = {
        row.skill: row
        for row in db.query(SkillScore).filter(SkillScore.player_id == player.id).all()
    }
    updates: dict[str, SkillDelta] = {}

    def _bump_into(skill_key: str, delta: float) -> None:
        row = skills_by_key.get(skill_key)
        if row is None:
            return
        before = row.score
        row.score = _bump_skill(row.score, delta)
        actual_delta = round(row.score - before, 2)
        if skill_key in updates:
            updates[skill_key] = SkillDelta(
                skill=updates[skill_key].skill,  # type: ignore[arg-type]
                delta=round(updates[skill_key].delta + actual_delta, 2),
                new_score=round(row.score, 2),
            )
        else:
            updates[skill_key] = SkillDelta(
                skill=skill_key,  # type: ignore[arg-type]
                delta=actual_delta,
                new_score=round(row.score, 2),
            )

    if all_passed:
        for skill_key in question.get("skill_focus") or []:
            _bump_into(skill_key, PASS_FOCUS_SKILL_BUMP)
    else:
        # Map primary_gap (or expected gap key) to a skill via the taxonomies.
        gap_skill = None
        for source_key in ("gap_taxonomy", "expected_gaps", "expected_subtasks"):
            for g in (question.get(source_key) or []):
                if g.get("key") == primary_gap:
                    gap_skill = g.get("skill")
                    if not gap_skill:
                        # subtask entries don't carry skill; fall back to skill_focus[0]
                        skill_focus = question.get("skill_focus") or []
                        gap_skill = skill_focus[0] if skill_focus else None
                    break
            if gap_skill:
                break
        if gap_skill:
            _bump_into(gap_skill, FAIL_GAP_SKILL_BUMP)

    return list(updates.values())


# ---------- Streak tracking ----------

def update_streak(player: Player, now: Optional[datetime] = None) -> None:
    now = now or datetime.utcnow()
    today = now.date()
    if player.last_active_at is None:
        player.current_streak = 1
    else:
        days_since = (today - player.last_active_at.date()).days
        if days_since <= 0:
            pass
        elif days_since == 1:
            player.current_streak = (player.current_streak or 0) + 1
        else:
            player.current_streak = 1
    player.longest_streak = max(player.longest_streak or 0, player.current_streak or 0)
    player.last_active_at = now


# ---------- Badges ----------

def _has_badge(db: Session, player_id: int, badge_key: str) -> bool:
    return (
        db.query(PlayerBadge)
        .filter(PlayerBadge.player_id == player_id, PlayerBadge.badge_key == badge_key)
        .first()
        is not None
    )


def _grant_badge(db: Session, player_id: int, badge_key: str) -> bool:
    if _has_badge(db, player_id, badge_key):
        return False
    db.add(PlayerBadge(player_id=player_id, badge_key=badge_key))
    return True


def grant_streak_badges(db: Session, player: Player) -> list[str]:
    earned: list[str] = []
    streak = player.current_streak or 0
    if streak >= 7 and _grant_badge(db, player.id, "week_warrior"):
        earned.append("week_warrior")
    if streak >= 30 and _grant_badge(db, player.id, "unstoppable"):
        earned.append("unstoppable")
    return earned


# ---------- Promotion ----------

def _ravi_promotion_body(display_name: str, new_title: str) -> str:
    return (
        f"{display_name}, I've been watching your progress. The consistency you've "
        f"shown with AI is exactly what NxtCorp looks for. Effective today, you are "
        f"{new_title}. Well deserved."
    )


# ---------- Employee of the Month (v3 — monthly) ----------
#
# Awarded at most once per calendar month per player, when ALL FIVE
# criteria are met by their activity within that month:
#   1. tasks_completed_this_month >= EOTM_MIN_TASKS
#   2. first_try_count_this_month >= EOTM_MIN_FIRST_TRY
#   3. clean_passes_this_month >= EOTM_MIN_CLEAN_PASSES
#      (clean = no Arjun chat message tied to that question this month)
#   4. longest_streak >= EOTM_MIN_STREAK at award time
#   5. no_l4_reveals_this_month == True
#      (no Priya L4 messages anywhere this month — i.e. they never had a
#      gap fully revealed for them)
#
# +200 XP, plus the employee_of_the_month badge for that month.

EOTM_MIN_TASKS = 3
EOTM_MIN_FIRST_TRY = 1
EOTM_MIN_CLEAN_PASSES = 2
EOTM_MIN_STREAK = 5
EOTM_XP_AWARD = 200


def _ravi_eotm_body(display_name: str) -> str:
    return (
        f"{display_name} — quick announcement. This month you've shipped tickets "
        "cleanly, hit your first-try targets, and kept the streak alive without "
        "leaning on hints. The team has taken note. I'm naming you Employee of "
        "the Month. Keep that independence — it's the rarest thing on this floor."
    )


def _current_year_month(now: Optional[datetime] = None) -> str:
    n = now or datetime.utcnow()
    return f"{n.year:04d}-{n.month:02d}"


def _month_window(year_month: str) -> tuple[datetime, datetime]:
    """Inclusive-start, exclusive-end UTC window for a YYYY-MM string."""
    y, m = year_month.split("-")
    start = datetime(int(y), int(m), 1)
    if int(m) == 12:
        end = datetime(int(y) + 1, 1, 1)
    else:
        end = datetime(int(y), int(m) + 1, 1)
    return start, end


def _compute_monthly_stats(
    db: Session, player_id: int, year_month: str,
) -> dict[str, Any]:
    start, end = _month_window(year_month)
    completions = (
        db.query(PlayerCompletedTask)
        .filter(
            PlayerCompletedTask.player_id == player_id,
            PlayerCompletedTask.completed_at >= start,
            PlayerCompletedTask.completed_at < end,
        )
        .all()
    )
    completed_qids_this_month = {c.question_id for c in completions}

    # First-try passes this month — Attempt rows with attempt_number == 1 +
    # all_passed for the questions completed this month.
    first_try_count = (
        db.query(Attempt)
        .filter(
            Attempt.player_id == player_id,
            Attempt.attempt_number == 1,
            Attempt.all_passed.is_(True),
            Attempt.created_at >= start,
            Attempt.created_at < end,
        )
        .count()
    )

    # Arjun messages this month — set of question_ids that triggered Arjun.
    arjun_qids_this_month = {
        m.related_question_id
        for m in db.query(ChatMessage)
        .filter(
            ChatMessage.player_id == player_id,
            ChatMessage.character == "arjun",
            ChatMessage.created_at >= start,
            ChatMessage.created_at < end,
        )
        .all()
        if m.related_question_id
    }
    clean_passes = sum(1 for qid in completed_qids_this_month if qid not in arjun_qids_this_month)

    # L4 reveals this month — count Attempt rows where Priya hit level 4.
    # We store L4 reveals as the ChatMessage with character='priya' and an
    # escalation context: easiest to detect via the related Attempt's
    # all_passed flag being False AND the message coming on attempt >= 5
    # post-Arjun. Cheap heuristic: look for the literal phrase "Here's what
    # got missed" which Priya's L4 rubric tells her to use — combined with
    # character==priya we get a reliable count without adding a column.
    l4_reveals = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.player_id == player_id,
            ChatMessage.character == "priya",
            ChatMessage.body.like("Here's what got missed%"),
            ChatMessage.created_at >= start,
            ChatMessage.created_at < end,
        )
        .count()
    )

    return {
        "tasks_completed": len(completed_qids_this_month),
        "first_try_count": first_try_count,
        "clean_passes":    clean_passes,
        "no_l4_reveals":   (l4_reveals == 0),
    }


def _eligible_for_eotm(stats: dict[str, Any], longest_streak: int) -> bool:
    return (
        stats["tasks_completed"] >= EOTM_MIN_TASKS
        and stats["first_try_count"] >= EOTM_MIN_FIRST_TRY
        and stats["clean_passes"] >= EOTM_MIN_CLEAN_PASSES
        and longest_streak >= EOTM_MIN_STREAK
        and stats["no_l4_reveals"]
    )


def _maybe_award_employee_of_the_month(
    db: Session,
    player: Player,
    question_id: str,
    related_attempt_id: Optional[int],
) -> list[str]:
    """Award EotM at most once per calendar month per player. Idempotent."""
    year_month = _current_year_month()
    existing = (
        db.query(EmployeeOfMonth)
        .filter(
            EmployeeOfMonth.player_id == player.id,
            EmployeeOfMonth.year_month == year_month,
        )
        .first()
    )
    if existing is not None:
        return []

    stats = _compute_monthly_stats(db, player.id, year_month)
    if not _eligible_for_eotm(stats, player.longest_streak or 0):
        return []

    db.add(EmployeeOfMonth(
        player_id=player.id,
        year_month=year_month,
        tasks_completed=stats["tasks_completed"],
        first_try_count=stats["first_try_count"],
        clean_passes=stats["clean_passes"],
        longest_streak=player.longest_streak or 0,
        no_l4_reveals=stats["no_l4_reveals"],
        xp_awarded=EOTM_XP_AWARD,
    ))
    player.total_xp = (player.total_xp or 0) + EOTM_XP_AWARD

    # One badge per month — key embeds the YYYY-MM so monthly history is
    # visible in the profile badge list.
    badge_key = f"employee_of_the_month_{year_month}"
    if _grant_badge(db, player.id, badge_key):
        # Also re-grant the generic key once, for back-compat with v2 UI
        # that looks for "employee_of_the_month" exactly.
        _grant_badge(db, player.id, "employee_of_the_month")

    db.add(ChatMessage(
        player_id=player.id,
        character="ravi",
        expression="proud",
        body=_ravi_eotm_body(player.display_name),
        related_question_id=question_id,
        related_attempt_id=related_attempt_id,
    ))
    return [badge_key]


def maybe_promote(
    db: Session,
    player: Player,
    question_id: str,
    related_attempt_id: Optional[int],
) -> tuple[Optional[int], list[str]]:
    skills = db.query(SkillScore).filter(SkillScore.player_id == player.id).all()
    overall = compute_overall_skill(skills)
    new_level = level_for_overall(overall)
    earned: list[str] = []
    if new_level <= (player.job_level or 1):
        return (None, earned)
    player.job_level = new_level
    new_title = job_title(new_level)
    db.add(
        ChatMessage(
            player_id=player.id,
            character="ravi",
            expression="proud",
            body=_ravi_promotion_body(player.display_name, new_title),
            related_question_id=question_id,
            related_attempt_id=related_attempt_id,
        )
    )
    if _grant_badge(db, player.id, "first_promotion"):
        earned.append("first_promotion")
    return (new_level, earned)


# ---------- Conversation loader ----------

def load_recent_messages(
    db: Session,
    player_id: int,
    question_id: str,
    limit: int = 4,
) -> list[dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.player_id == player_id,
            ChatMessage.related_question_id == question_id,
        )
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {"character": m.character, "body": m.body, "expression": m.expression or ""}
        for m in rows
    ]


# ---------- Per-type result container ----------

class TypeRunResult:
    """Normalized output of any per-type runner. Feeds the shared persistence
    + coach + RunResponse builders.
    """

    def __init__(
        self,
        *,
        code: Optional[str],
        outcomes: list[TestOutcome],
        sample_total: int,
        sample_passed: int,
        hidden_total: int,
        hidden_passed: int,
        all_passed: bool,
        primary_gap: Optional[str],
        requirement_score: float,
        output_score: float,
        coach_reasoning: str,
        student_summary: str,
        # v5: full assessment carries per-type score detail + flags so the
        # orchestrator can ship the public-safe subset to the frontend.
        assessment: Optional["AssessmentResult"] = None,
    ):
        self.code = code
        self.outcomes = outcomes
        self.sample_total = sample_total
        self.sample_passed = sample_passed
        self.hidden_total = hidden_total
        self.hidden_passed = hidden_passed
        self.all_passed = all_passed
        self.primary_gap = primary_gap
        self.requirement_score = requirement_score
        self.output_score = output_score
        self.coach_reasoning = coach_reasoning
        self.student_summary = student_summary
        self.assessment = assessment

    @property
    def overall_score(self) -> float:
        return round(0.6 * self.requirement_score + 0.4 * self.output_score, 2)


# ---------- Type 3 — Specify and Execute (existing path) ----------

def _run_type_3(
    question: dict[str, Any],
    student_prompt: str,
    *,
    exercise_type: int = 1,
) -> TypeRunResult:
    """v6 Type 1 (Prompt AI to Build) / Type 5 (Improve After Failure).

    No hidden_tests anymore. Sample tests still run against the generated
    code so the UI can show pass/fail rows, but they are NOT used for
    scoring — Zara reasons about the code directly.
    `all_passed` is redefined as `zara.overall_score >= 7.5`.
    """
    fn_name = function_name_from_signature(question)
    sample_tests = list(question.get("sample_tests") or [])
    sample_count = len(sample_tests)

    gen = generate_code(student_prompt, question)
    # Sample tests are informational only — for UI feedback. Run them so
    # the student sees per-test rows but don't gate scoring on them.
    if sample_tests:
        execution = execute(gen.code, fn_name, sample_tests, timeout_seconds=5)
    else:
        execution = ExecutionResult(outcomes=[])

    assessment = assess(
        student_prompt, question, execution,
        exercise_type=exercise_type,
        generated_code=gen.code,
    )

    sample_passed = sum(1 for o in execution.outcomes if o.passed)

    # v6: passing condition is Zara's overall_score >= 7.5. Drives all
    # downstream mechanics (XP, mark_completed, promotion, EotM).
    all_passed = bool(assessment.overall_score >= 7.5)

    return TypeRunResult(
        code=gen.code,
        outcomes=execution.outcomes,
        sample_total=sample_count,
        sample_passed=sample_passed,
        hidden_total=0,
        hidden_passed=0,
        all_passed=all_passed,
        primary_gap=assessment.primary_gap,
        requirement_score=assessment.requirement_score,
        output_score=assessment.output_score,
        coach_reasoning=assessment.reasoning,
        student_summary=student_prompt,
        assessment=assessment,
    )


# ---------- Type 5 — Diagnose and Fix (Type 3 + improvement context) ----------

def _run_type_5(question: dict[str, Any], student_prompt: str) -> TypeRunResult:
    return _run_type_3(question, student_prompt, exercise_type=5)


# ---------- Type 2 — Decompose Vague Work (v6: pure Zara LLM) ----------

def _run_type_1(question: dict[str, Any], subtasks: list[str]) -> TypeRunResult:
    """v6: no reference_decomposition / no Judge. Zara reads the meeting +
    student's sub-tasks directly and scores. Empty execution facsimile
    since there's no code-running axis for Decompose.
    """
    summary = (
        "Subtasks:\n" + "\n".join(f"- {s}" for s in (subtasks or []))
    ) if subtasks else "(empty)"

    assessment = assess(
        summary, question, ExecutionResult(outcomes=[]),
        exercise_type=2,
    )
    all_passed = bool(assessment.overall_score >= 7.5)

    return TypeRunResult(
        code=None,
        outcomes=[],
        sample_total=0,
        sample_passed=0,
        hidden_total=0,
        hidden_passed=0,
        all_passed=all_passed,
        primary_gap=assessment.primary_gap,
        requirement_score=assessment.requirement_score,
        output_score=assessment.output_score,
        coach_reasoning=assessment.reasoning,
        student_summary=summary,
        assessment=assessment,
    )


# ---------- Type 3 — Predict AI Failure (v6: pure Zara LLM) ----------

def _run_type_2(question: dict[str, Any], identified_gaps: list[str]) -> TypeRunResult:
    """v6: no reference_failure_cases / no Judge. Zara reads the meeting +
    the flawed AI code (from `ai_code_shown`) + the student's predictions
    and scores via LLM reasoning.
    """
    summary = (
        "Identified gaps:\n" + "\n".join(f"- {g}" for g in (identified_gaps or []))
    ) if identified_gaps else "(empty)"

    assessment = assess(
        summary, question, ExecutionResult(outcomes=[]),
        exercise_type=3,
    )
    all_passed = bool(assessment.overall_score >= 7.5)

    return TypeRunResult(
        code=None,
        outcomes=[],
        sample_total=0,
        sample_passed=0,
        hidden_total=0,
        hidden_passed=0,
        all_passed=all_passed,
        primary_gap=assessment.primary_gap,
        requirement_score=assessment.requirement_score,
        output_score=assessment.output_score,
        coach_reasoning=assessment.reasoning,
        student_summary=summary,
        assessment=assessment,
    )


# ---------- Type 4 — Verify ----------

def _run_type_4(question: dict[str, Any], test_cases: list[dict[str, Any]]) -> TypeRunResult:
    """Student writes test cases. We run `target_code` against each, then
    score: each student case must produce the same output as `reference_code`
    (i.e. the student's `expected` is correct), AND the student's input set
    must cover the gap_taxonomy (via the question's hidden_tests).
    """
    """v6 Type 4 — Verify AI Output.

    No reference_solution available. Zara reasons about whether the student's
    test cases would catch bugs in `buggy_ai_code` based on the meeting +
    the buggy code + the test cases. Sample tests (student's own cases) are
    still run against the buggy code so the UI can show pass/fail rows,
    but the result is NOT used for scoring.
    """
    buggy_code = question.get("buggy_ai_code") or question.get("target_code", "")
    fn_name = function_name_from_signature(question)
    cases = test_cases or []

    outcomes: list[TestOutcome] = []
    if cases and buggy_code:
        # Run student tests against buggy code purely so the UI rows reflect
        # whether each (input → expected) matches the buggy implementation.
        buggy_exec = execute(
            buggy_code, fn_name,
            [{"input": c["input"], "expected": c["expected"]} for c in cases],
            timeout_seconds=5,
        )
        for case, b_out in zip(cases, buggy_exec.outcomes):
            outcomes.append(TestOutcome(
                input=case["input"],
                expected=case["expected"],
                actual=b_out.actual if b_out.error is None else f"error: {b_out.error}",
                passed=bool(b_out.passed),
                error=b_out.error,
            ))

    summary = (
        "Test cases:\n" + "\n".join(
            f"- input={c['input']!r} expected={c['expected']!r}" for c in cases
        )
    ) if cases else "(empty)"

    assessment = assess(
        summary, question, ExecutionResult(outcomes=outcomes),
        exercise_type=4,
    )
    all_passed = bool(assessment.overall_score >= 7.5)

    return TypeRunResult(
        code=buggy_code,
        outcomes=outcomes,
        sample_total=len(cases),
        sample_passed=sum(1 for o in outcomes if o.passed),
        hidden_total=0,
        hidden_passed=0,
        all_passed=all_passed,
        primary_gap=assessment.primary_gap,
        requirement_score=assessment.requirement_score,
        output_score=assessment.output_score,
        coach_reasoning=assessment.reasoning,
        student_summary=summary,
        assessment=assessment,
    )


# ---------- Coach input adapter ----------

def _execution_facsimile(type_result: TypeRunResult) -> ExecutionResult:
    return ExecutionResult(outcomes=type_result.outcomes)


def _assessment_facsimile(type_result: TypeRunResult) -> AssessmentResult:
    if type_result.assessment is not None:
        return type_result.assessment
    missing = [type_result.primary_gap] if type_result.primary_gap else []
    return AssessmentResult(
        gaps=missing,
        gaps_covered=[],
        gaps_missing=missing,
        omissions=[],
        commissions=[],
        requirement_quality=type_result.requirement_score,
        output_quality=type_result.output_score,
        overall_score=type_result.overall_score,
        primary_gap=type_result.primary_gap,
        zara_note=type_result.coach_reasoning,
        raw_response="",
        input_tokens=0,
        output_tokens=0,
    )


# ---------- Orchestrator ----------

def run_attempt(
    db: Session,
    player: Player,
    question_id: str,
    payload: dict[str, Any],
    attempt_number: int,
) -> RunResponse:
    """`payload` carries the type-specific fields:
      Type 1: {"subtasks": [str, ...]}
      Type 2: {"identified_gaps": [str, ...]}
      Type 3: {"student_prompt": "..."}
      Type 4: {"test_cases": [{"input": ..., "expected": ...}, ...]}
      Type 5: {"student_prompt": "..."}
    """
    question = load_question(question_id)
    exercise_type = int(question.get("exercise_type", 1))

    # v3 type → handler mapping (renumbered).
    # The _run_type_* function names below preserve the implementation
    # identities from v2; only the integer label maps differently now.
    #   v3 type 1 (Prompt AI to Build)     -> _run_type_3 (codegen + executor + assessor)
    #   v3 type 2 (Decompose)              -> _run_type_1 (subtask coverage)
    #   v3 type 3 (Predict AI Failure)     -> _run_type_2 (gap coverage)
    #   v3 type 4 (Verify AI Output)       -> _run_type_4 (test-case match)
    #   v3 type 5 (Improve AI After Fail)  -> _run_type_5 (codegen + executor + assessor)
    if exercise_type == 1:
        result = _run_type_3(question, str(payload.get("student_prompt") or ""), exercise_type=1)
    elif exercise_type == 2:
        result = _run_type_1(question, payload.get("subtasks") or [])
    elif exercise_type == 3:
        result = _run_type_2(question, payload.get("identified_gaps") or [])
    elif exercise_type == 4:
        result = _run_type_4(question, payload.get("test_cases") or [])
    elif exercise_type == 5:
        result = _run_type_5(question, str(payload.get("student_prompt") or ""))
    else:
        result = _run_type_3(question, str(payload.get("student_prompt") or ""))

    # v3 hybrid ladder: Arjun fires AT MOST ONCE per task. Check whether he's
    # already fired on this question for this player before dispatching.
    arjun_already_fired = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.player_id == player.id,
            ChatMessage.related_question_id == question_id,
            ChatMessage.character == "arjun",
        )
        .first()
        is not None
    )

    history = load_recent_messages(db, player.id, question_id)
    # v6: build attempt_history for Priya's decision logic (progress / stuck
    # / misunderstand). Read prior Attempt rows for this player+question.
    prior_attempts = (
        db.query(Attempt)
        .filter(Attempt.player_id == player.id, Attempt.question_id == question_id)
        .order_by(Attempt.attempt_number.asc())
        .all()
    )
    attempt_history = [
        {
            "attempt_number": a.attempt_number,
            "requirement_quality": float(a.requirement_score or 0.0),
            "output_quality": float(a.output_score or 0.0),
            "overall_score": float(a.overall_score or 0.0),
        }
        for a in prior_attempts
    ]

    who, level = compute_step(result.all_passed, attempt_number, arjun_already_fired)
    if who == "arjun":
        # v3 multi-turn flow: Arjun only opens with the static greeting
        # here; the actual conversation (casual round + directional hint)
        # is driven by the frontend through /api/coffee/turn. The Arjun
        # ChatMessage row this creates is what the XP-cap logic uses to
        # detect "Arjun helped on this task".
        coach_reply = coach_arjun_greeting(player.display_name)
    else:
        coach_reply = coach(
            student_display_name=player.display_name,
            question=question,
            student_prompt=result.student_summary,
            execution=_execution_facsimile(result),
            assessment=_assessment_facsimile(result),
            attempt_number=attempt_number,
            conversation_history=history,
            exercise_type=exercise_type,
            arjun_fired=arjun_already_fired,
            attempt_history=attempt_history,
            all_passed_override=result.all_passed,
        )

    # v3 L4 auto-complete: when Priya hits Level 4 (reveal), the task
    # terminates — student gets credit (reduced XP via the arjun_helped /
    # late-attempt rules below). The reveal IS the end of the task.
    l4_terminates = (who == "priya" and level == 4 and not result.all_passed)

    # Progression: skills, streak, XP, badges.
    skill_updates = apply_skill_updates(db, player, question, result.primary_gap, result.all_passed)
    update_streak(player)
    xp_base, badges_from_xp = compute_xp_base(result.all_passed, attempt_number)
    if result.all_passed and (player.current_streak or 0) >= 2:
        xp_earned = int(round(xp_base * (1 + STREAK_BONUS_RATE)))
    else:
        xp_earned = xp_base
    # v3 rule: if Arjun helped on this task at any point (or fires now),
    # cap XP and strip the first_try badge — leaning on the hint means
    # the student didn't solve it cold.
    arjun_helped = arjun_already_fired or (who == "arjun")
    if result.all_passed and arjun_helped:
        xp_earned = min(xp_earned, ARJUN_HELP_XP_CAP)
        # Don't award first_try when Arjun pre-loaded the answer category.
        badges_from_xp = [b for b in badges_from_xp if b != "first_try"]

    # v3: phase-aware XP multiplier (applied after Arjun cap so the cap
    # remains the hard ceiling).
    xp_earned = int(round(xp_earned * phase_xp_multiplier(player)))
    if arjun_helped and result.all_passed:
        xp_earned = min(xp_earned, ARJUN_HELP_XP_CAP)
    player.total_xp = (player.total_xp or 0) + xp_earned

    badges_earned: list[str] = []
    for key in badges_from_xp:
        if _grant_badge(db, player.id, key):
            badges_earned.append(key)
    badges_earned.extend(grant_streak_badges(db, player))

    # Persist Attempt row first.
    attempt = Attempt(
        player_id=player.id,
        question_id=question_id,
        attempt_number=attempt_number,
        exercise_type=exercise_type,
        student_prompt=result.student_summary,
        generated_code=result.code,
        test_results={
            "sample_passed": result.sample_passed,
            "sample_total": result.sample_total,
            "hidden_passed": result.hidden_passed,
            "hidden_total": result.hidden_total,
        },
        requirement_score=result.requirement_score,
        output_score=result.output_score,
        overall_score=result.overall_score,
        primary_gap=result.primary_gap,
        all_passed=result.all_passed,
        xp_earned=xp_earned,
        arjun_triggered=bool(arjun_helped),
    )
    db.add(attempt)
    db.flush()

    eom_year_month: Optional[str] = None
    if result.all_passed:
        mark_completed(db, player, question_id, attempts_taken=attempt_number)
        # Employee of the Month — v3 monthly award, granted once per calendar
        # month when all 5 criteria met. Ravi Sir announces it.
        eom_badges = _maybe_award_employee_of_the_month(db, player, question_id, attempt.id)
        if eom_badges:
            badges_earned.extend(eom_badges)
            eom_year_month = _current_year_month()
    elif l4_terminates:
        # v3: L4 reveal IS the end of the task. The student got the gap
        # spelled out — they're not solving this one cold. Move on. They
        # keep the consolation XP from compute_xp_base() and forfeit
        # first_try / EotM eligibility for this task.
        mark_completed(db, player, question_id, attempts_taken=attempt_number)

    new_level, promo_badges = maybe_promote(db, player, question_id, attempt.id)
    badges_earned.extend(promo_badges)

    # v3 phase advancement: check thresholds after the skill bumps are
    # persisted. No badge, no chat message — phase is a quiet rail behind
    # the existing job_level cinematic. The frontend reads it from profile.
    maybe_advance_phase(db, player)

    db.add(
        ChatMessage(
            player_id=player.id,
            character="player",
            expression=None,
            body=result.student_summary,
            related_question_id=question_id,
            related_attempt_id=attempt.id,
        )
    )
    db.add(
        ChatMessage(
            player_id=player.id,
            character="arjun" if who == "arjun" else "priya",
            expression=coach_reply.expression,
            body=coach_reply.body,
            related_question_id=question_id,
            related_attempt_id=attempt.id,
        )
    )
    db.commit()
    db.refresh(player)

    # v3: hidden tests NEVER appear in the UI rows — only the sample tests.
    # Slice every type to sample_total. For coverage-style types (Decompose /
    # Predict / Verify) `outcomes` already equals sample_total, so this is
    # a no-op there. For codegen-style types (Prompt AI to Build, Improve
    # After Failure) it drops the hidden suffix. The aggregate counts
    # (`hidden_passed` / `hidden_total`) still flow through the response
    # so the UI can show "Hidden 2/4 (50%)" as a summary.
    ui_outcomes = result.outcomes[: result.sample_total]

    test_results: list[TestCaseResult] = []
    for o in ui_outcomes:
        test_results.append(
            TestCaseResult(
                input=o.input,
                expected=o.expected,
                actual=o.actual,
                passed=o.passed,
                error=o.error,
            )
        )

    # v5 — build the PUBLIC-SAFE Zara payload for the frontend. We send
    # scores + flags + a brief status_message ONLY. Never primary_gap,
    # gaps_covered, gaps_missing, or zara_note (those stay internal so
    # Priya can do her coaching without revealing the answer).
    zara_payload = _build_public_zara_payload(result, exercise_type)

    return RunResponse(
        attempt_id=attempt.id,
        test_results=test_results,
        sample_passed=result.sample_passed,
        sample_total=result.sample_total,
        hidden_passed=result.hidden_passed,
        hidden_total=result.hidden_total,
        all_passed=result.all_passed,
        xp_earned=xp_earned,
        badges_earned=badges_earned,
        skill_updates=skill_updates,
        coach_message=CoachMessage(
            character=("arjun" if who == "arjun" else "priya"),  # type: ignore[arg-type]
            expression=coach_reply.expression,  # type: ignore[arg-type]
            body=coach_reply.body,
            escalation_level=coach_reply.escalation_level,
        ),
        primary_gap=result.primary_gap,
        arjun_triggered=bool(arjun_helped),
        employee_of_month_awarded=eom_year_month,
        zara_assessment=zara_payload,
    )


# ---------- Public Zara payload builder ----------

def _build_public_zara_payload(
    result: "TypeRunResult",
    exercise_type: int,
) -> dict[str, Any]:
    """Compose the safe-for-frontend Zara payload.

    Includes: scores (requirement_quality, output_quality, overall_score),
    type_specific sub-scores, accidentally_passing_flag, eval_warning,
    status_message, status_kind (drives avatar expression + icon).

    Excludes: primary_gap, zara_note, gaps_covered, gaps_missing.
    """
    a = result.assessment
    if a is not None:
        req_q = float(a.requirement_quality)
        out_q = float(a.output_quality)
        overall = float(a.overall_score)
        type_specific = dict(a.type_specific or {})
        accidental = bool(a.accidentally_passing_flag)
        eval_warning = bool(a.eval_warning)
    else:
        # Coverage-style fallback for types 2/3 when assess() wasn't called.
        req_q = float(result.requirement_score)
        out_q = float(result.output_score)
        overall = float(result.overall_score)
        type_specific = {}
        accidental = False
        eval_warning = False

    # Per-type sub-keys + ensure structure exists.
    if exercise_type in (1, 5):
        type_specific.setdefault("tests_passed", result.sample_passed + result.hidden_passed)
        type_specific.setdefault("tests_total", result.sample_total + result.hidden_total)
        total = type_specific["tests_total"] or 0
        type_specific.setdefault(
            "test_pass_rate",
            round((type_specific["tests_passed"] / total) * 100.0, 1) if total else 0.0,
        )

    # Status message: never reveals internals. Avatar expression derived.
    if eval_warning:
        status_message = "QA assessment needs review. Priya will follow up."
        status_kind = "warning"
    elif accidental:
        status_message = "Some test cases have unexpected expected values. Priya will follow up."
        status_kind = "warning"
    elif result.all_passed:
        status_message = "All checks passed. Good work."
        status_kind = "pass"
    else:
        status_message = "QA caught something. Priya will follow up."
        status_kind = "fail"

    return {
        "exercise_type": f"type_{exercise_type}",
        "scores": {
            "requirement_quality": round(req_q, 1),
            "output_quality": round(out_q, 1),
            "overall_score": round(overall, 1),
            "type_specific": type_specific,
        },
        "accidentally_passing_flag": accidental,
        "eval_warning": eval_warning,
        "status_message": status_message,
        "status_kind": status_kind,
    }


__all__ = [
    "run_attempt",
    "apply_skill_updates",
    "update_streak",
    "grant_streak_badges",
    "maybe_promote",
    "compute_xp_base",
    "load_recent_messages",
]
