"""Task endpoints (step 6, extended for type 1/2/4/5).

GET  /api/task/current   -> the player's current exercise, with type-specific fields
POST /api/task/run       -> submit an attempt; backend dispatches by exercise_type
POST /api/task/respond   -> chat-only reply to Priya's Socratic question
"""

from __future__ import annotations

import logging
import traceback
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.agents.coach import coach_followup, coach_hint_arjun
from backend.core.llm import LLMError

logger = logging.getLogger("nxtcorp.task")
from backend.auth.deps import CurrentPlayer
from backend.core.question_loader import (
    QuestionNotFoundError,
    load_question,
)
from backend.db.database import get_db
from backend.db.models import Attempt, ChatMessage, PlayerMeetingCompletion
from backend.models.schemas import (
    CoachMessage,
    HintResponse,
    RespondRequest,
    RespondResponse,
    RunRequest,
    RunResponse,
    SampleTest,
    TaskView,
)


# spec v2: Arjun's hint is FREE — auto-triggered after 2 Priya Socratic
# rounds fail. Cost kept as a constant in case we re-introduce a paid mode.
HINT_COST_XP = 0
from backend.services.question_progression import current_question_id_for
from backend.services.run_pipeline import load_recent_messages, run_attempt


router = APIRouter(prefix="/api/task", tags=["task"])


@router.get("/current", response_model=TaskView)
def get_current_task(
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> TaskView:
    question_id = current_question_id_for(db, player)
    try:
        question = load_question(question_id)
    except QuestionNotFoundError:
        raise HTTPException(status_code=404, detail=f"question '{question_id}' not found")

    sample_tests = [
        SampleTest(input=t["input"], expected=t["expected"], description=t.get("description"))
        for t in (question.get("sample_tests") or [])
    ]
    framing = question.get("framing") or {}
    exercise_type = int(question.get("exercise_type", 3))

    # Type-specific extras. v3 numbering: 2 = Decompose, 3 = Predict AI Failure.
    # We deliberately do NOT leak gap_taxonomy keys/descriptions for Type 3 —
    # the student must FIND them. For Type 2, we send only a count hint, not
    # the subtask descriptions themselves.
    expected_subtasks_count = None
    if exercise_type == 2:
        expected_subtasks_count = len(question.get("expected_subtasks") or [])

    expected_gaps_count = None
    if exercise_type == 3:
        expected_gaps_count = len(question.get("expected_gaps") or [])

    # v3 FIX 2: prefer the task-specific `priya_framing` string when present.
    # Falls back to the generic `framing.message` for legacy questions that
    # haven't been updated with a custom Priya line yet.
    framing_message = (
        question.get("priya_framing")
        or framing.get("message", "")
    )

    raw_script = question.get("meeting_script") or []
    meeting_script = raw_script if isinstance(raw_script, list) else []

    # v5: has this player already finished the meeting for this question?
    meeting_done = (
        db.query(PlayerMeetingCompletion)
        .filter(
            PlayerMeetingCompletion.player_id == player.id,
            PlayerMeetingCompletion.question_id == question["question_id"],
        )
        .first()
        is not None
    )

    return TaskView(
        question_id=question["question_id"],
        exercise_type=exercise_type,  # type: ignore[arg-type]
        title=question.get("title", ""),
        framing_character=framing.get("character", "priya"),  # type: ignore[arg-type]
        framing_message=framing_message,
        priya_chat_message=question.get("priya_chat_message"),
        meeting_script=meeting_script,
        meeting_completed=meeting_done,
        problem_description=question.get("problem_description", ""),
        sample_tests=sample_tests,
        function_signature=question.get("function_signature"),
        notes=question.get("notes"),
        flawed_prompt=question.get("flawed_prompt") if exercise_type == 3 else None,
        target_code=question.get("target_code") if exercise_type == 4 else None,
        failing_prompt=question.get("failing_prompt") if exercise_type == 5 else None,
        failing_inputs_hint=question.get("failing_inputs_hint") if exercise_type == 5 else None,
        expected_subtasks_count=expected_subtasks_count,
        expected_gaps_count=expected_gaps_count,
    )


@router.post("/run", response_model=RunResponse)
def post_run(
    payload: RunRequest,
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> RunResponse:
    question_id = current_question_id_for(db, player)
    try:
        return run_attempt(
            db=db,
            player=player,
            question_id=question_id,
            payload=payload.model_dump(exclude_none=True),
            attempt_number=payload.attempt_number,
        )
    except QuestionNotFoundError:
        raise HTTPException(status_code=404, detail=f"question '{question_id}' not found")
    except LLMError as e:
        # Upstream LLM call failed after the shim's retries. Log the full
        # cause for backend ops, but show the student a clean message —
        # no raw error codes leaking into the chat banner.
        logger.error("LLM error during /run for player=%s question=%s: %s",
                     player.id, question_id, e)
        raise HTTPException(
            status_code=502,
            detail="AI is temporarily unavailable. Please try submitting again.",
        )
    except HTTPException:
        raise
    except Exception as e:
        # Any other unhandled error — log full traceback to backend console
        # so the real cause is visible, then return a clean 500 with detail.
        tb = traceback.format_exc()
        logger.error(
            "Unhandled error in /run for player=%s question=%s attempt=%s:\n%s",
            player.id, question_id, payload.attempt_number, tb,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Run pipeline failed: {type(e).__name__}: {e}",
        )


@router.post("/meeting/complete")
def post_meeting_complete(
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """v5: mark the meeting for this player + current question as completed.

    Idempotent — repeated calls are a no-op once the row exists. After this
    the TaskView will return `meeting_completed=true` so the frontend hides
    the "Join Meeting →" CTA for the rest of this ticket.
    """
    question_id = current_question_id_for(db, player)
    existing = (
        db.query(PlayerMeetingCompletion)
        .filter(
            PlayerMeetingCompletion.player_id == player.id,
            PlayerMeetingCompletion.question_id == question_id,
        )
        .first()
    )
    if existing is None:
        db.add(PlayerMeetingCompletion(player_id=player.id, question_id=question_id))
        db.commit()
    return {"question_id": question_id, "meeting_completed": True}


@router.post("/hint", response_model=HintResponse)
def post_hint(
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> HintResponse:
    """Receive Arjun's whispered directional hint. v2: free.

    Auto-trigger flow lives in run_pipeline; this endpoint stays as a manual
    fallback (cost == 0) for explicit player request. Returns 402 only if a
    future configuration re-introduces a positive HINT_COST_XP.
    """
    if HINT_COST_XP > 0 and (player.total_xp or 0) < HINT_COST_XP:
        raise HTTPException(
            status_code=402,
            detail=f"Not enough XP for a hint. Need {HINT_COST_XP}, have {player.total_xp or 0}.",
        )

    question_id = current_question_id_for(db, player)
    try:
        question = load_question(question_id)
    except QuestionNotFoundError:
        raise HTTPException(status_code=404, detail=f"question '{question_id}' not found")

    # Pull most-recent attempt for context: its prompt + primary_gap.
    last_attempt = (
        db.query(Attempt)
        .filter(Attempt.player_id == player.id, Attempt.question_id == question_id)
        .order_by(Attempt.id.desc())
        .first()
    )
    primary_gap = last_attempt.primary_gap if last_attempt else None
    last_prompt = last_attempt.student_prompt if last_attempt else None

    reply = coach_hint_arjun(
        student_display_name=player.display_name,
        question=question,
        primary_gap=primary_gap,
        last_attempt_prompt=last_prompt,
    )

    # Charge the player AFTER we have the hint in hand — so we don't deduct
    # XP if the LLM blew up. (coach_hint_arjun has a fallback body, so this
    # path always returns something.)
    player.total_xp = (player.total_xp or 0) - HINT_COST_XP

    # Persist Arjun's message in chat so the conversation history reflects it.
    db.add(
        ChatMessage(
            player_id=player.id,
            character="arjun",
            expression="happy",
            body=reply.body,
            related_question_id=question_id,
            related_attempt_id=last_attempt.id if last_attempt else None,
        )
    )
    db.commit()
    db.refresh(player)

    return HintResponse(
        hint_message=reply.body,
        xp_deducted=HINT_COST_XP,
        xp_remaining=player.total_xp,
    )


@router.post("/respond", response_model=RespondResponse)
def post_respond(
    payload: RespondRequest,
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> RespondResponse:
    question_id = current_question_id_for(db, player)
    try:
        question = load_question(question_id)
    except QuestionNotFoundError:
        raise HTTPException(status_code=404, detail=f"question '{question_id}' not found")

    history = load_recent_messages(db, player.id, question_id, limit=6)

    last_attempt = (
        db.query(Attempt)
        .filter(Attempt.player_id == player.id, Attempt.question_id == question_id)
        .order_by(Attempt.id.desc())
        .first()
    )
    primary_gap = last_attempt.primary_gap if last_attempt else None

    reply = coach_followup(
        student_display_name=player.display_name,
        student_text=payload.student_response,
        question=question,
        conversation_history=history,
        primary_gap=primary_gap,
    )

    db.add(
        ChatMessage(
            player_id=player.id,
            character="player",
            expression=None,
            body=payload.student_response,
            related_question_id=question_id,
            related_attempt_id=last_attempt.id if last_attempt else None,
        )
    )
    db.add(
        ChatMessage(
            player_id=player.id,
            character="priya",
            expression=reply.expression,
            body=reply.body,
            related_question_id=question_id,
            related_attempt_id=last_attempt.id if last_attempt else None,
        )
    )
    db.commit()

    return RespondResponse(
        coach_followup=CoachMessage(
            character="priya",
            expression=reply.expression,  # type: ignore[arg-type]
            body=reply.body,
            escalation_level=reply.escalation_level,
        )
    )
