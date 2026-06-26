"""Onboarding endpoint (step 8).

Day 1 of the NxtCorp narrative. The student finishes the onboarding flow on
the frontend (name → avatar → pronouns), then POSTs to /api/onboarding/complete
to commit those choices and mark them as done. Two story events are recorded
so we know they've already seen Priya's welcome and Arjun's intro.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.deps import CurrentPlayer
from backend.db.database import get_db
from backend.db.models import PlayerStoryEvent
from backend.models.schemas import (
    OnboardingCompleteRequest,
    PlayerProfile,
)
from backend.services.profile import build_player_profile


router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


DAY1_EVENT_KEYS = ("day1_priya_welcome", "day1_arjun_intro")


@router.post("/complete", response_model=PlayerProfile)
def complete_onboarding(
    payload: OnboardingCompleteRequest,
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> PlayerProfile:
    if player.onboarding_done:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding already complete",
        )

    player.display_name = payload.display_name
    player.avatar_id = payload.avatar_id
    player.pronouns = payload.pronouns
    player.job_role = payload.job_role
    player.onboarding_done = True

    existing = {
        e.event_key
        for e in db.query(PlayerStoryEvent)
        .filter(PlayerStoryEvent.player_id == player.id)
        .all()
    }
    for key in DAY1_EVENT_KEYS:
        if key not in existing:
            db.add(PlayerStoryEvent(player_id=player.id, event_key=key))

    db.commit()
    db.refresh(player)

    return build_player_profile(db, player)
