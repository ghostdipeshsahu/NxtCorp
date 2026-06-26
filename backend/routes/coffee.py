"""Coffee corner endpoints — Arjun multi-turn conversation (v3).

The student gets pulled into the coffee corner after the 3rd failed Priya
attempt (auto-fire). The frontend drives a 3-step conversation through
this single endpoint, picking from fixed option strings each round.

Rounds (all bodied by the Priya Coach Agent's Arjun voice register —
Arjun is NOT a separate agent):

  0 (open)     → fixed greeting, returns Round 1 options. No LLM call.
  1 (reply)    → casual reply to student's R1 choice, returns R2 options.
  2 (hint)     → directional hint + static closing line. is_final=True.

XP cap (40 when Arjun helps) is enforced in run_pipeline — this route
only owns the conversation surface.
"""

from __future__ import annotations

import logging
import traceback
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.agents.coach import (
    ARJUN_CLOSING_LINE,
    ROUND_1_OPTIONS,
    ROUND_2_OPTIONS,
    coach_arjun_greeting,
    coach_arjun_hint,
    coach_arjun_round1_reply,
)
from backend.auth.deps import CurrentPlayer
from backend.core.llm import LLMError
from backend.core.question_loader import QuestionNotFoundError, load_question
from backend.db.database import get_db
from backend.db.models import Attempt
from backend.services.question_progression import current_question_id_for


router = APIRouter(prefix="/api/coffee", tags=["coffee"])
logger = logging.getLogger("nxtcorp.coffee")


class CoffeeTurnRequest(BaseModel):
    round: int = Field(ge=0, le=2)
    choice: Optional[str] = None


class CoffeeTurnResponse(BaseModel):
    round: int
    arjun_message: str
    options: list[str]
    is_final: bool


def _latest_primary_gap(db: Session, player_id: int, question_id: str) -> Optional[str]:
    """Most recent failing attempt's primary_gap for this player+question.
    None if no recorded attempt has a gap yet (e.g. before any submit).
    """
    row = (
        db.query(Attempt)
        .filter(
            Attempt.player_id == player_id,
            Attempt.question_id == question_id,
        )
        .order_by(Attempt.id.desc())
        .first()
    )
    if row is None:
        return None
    return row.primary_gap


@router.post("/turn", response_model=CoffeeTurnResponse)
def post_turn(
    payload: CoffeeTurnRequest,
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> CoffeeTurnResponse:
    question_id = current_question_id_for(db, player)
    try:
        question = load_question(question_id)
    except QuestionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"question '{question_id}' not found",
        )

    try:
        if payload.round == 0:
            reply = coach_arjun_greeting(player.display_name)
            return CoffeeTurnResponse(
                round=0,
                arjun_message=reply.body,
                options=list(ROUND_1_OPTIONS),
                is_final=False,
            )

        if payload.round == 1:
            choice = (payload.choice or "").strip() or ROUND_1_OPTIONS[0]
            reply = coach_arjun_round1_reply(
                student_display_name=player.display_name,
                question=question,
                student_choice=choice,
            )
            return CoffeeTurnResponse(
                round=1,
                arjun_message=reply.body,
                options=list(ROUND_2_OPTIONS),
                is_final=False,
            )

        # Round 2 — hint + static closing
        choice = (payload.choice or "").strip() or ROUND_2_OPTIONS[0]
        primary_gap = _latest_primary_gap(db, player.id, question_id)
        reply = coach_arjun_hint(
            student_display_name=player.display_name,
            question=question,
            primary_gap=primary_gap,
            student_choice=choice,
        )
        full_message = reply.body.rstrip() + "\n\n" + ARJUN_CLOSING_LINE
        return CoffeeTurnResponse(
            round=2,
            arjun_message=full_message,
            options=[],
            is_final=True,
        )

    except LLMError as e:
        logger.error("LLM error during /coffee/turn for player=%s: %s", player.id, e)
        raise HTTPException(
            status_code=502,
            detail="AI is temporarily unavailable. Please try submitting again.",
        )
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Unhandled error in /coffee/turn for player=%s:\n%s", player.id, tb)
        raise HTTPException(
            status_code=500,
            detail=f"Coffee turn failed: {type(e).__name__}: {e}",
        )
