"""Story endpoints (step 10).

GET  /api/story/current   -> current act/day + pending events the player should see
POST /api/story/advance   -> mark an event seen; grant XP unless skipped
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.deps import CurrentPlayer
from backend.db.database import get_db
from backend.models.schemas import (
    StoryAdvanceRequest,
    StoryAdvanceResponse,
    StoryState,
)
from backend.services.story import advance as advance_story
from backend.services.story import get_pending_events


router = APIRouter(prefix="/api/story", tags=["story"])


@router.get("/current", response_model=StoryState)
def get_current(
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> StoryState:
    pending = get_pending_events(db, player)
    return StoryState(
        act=player.story_act or 1,
        day=player.story_day or 1,
        pending_events=pending,
    )


@router.post("/advance", response_model=StoryAdvanceResponse)
def post_advance(
    payload: StoryAdvanceRequest,
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> StoryAdvanceResponse:
    xp, day, act = advance_story(db, player, payload.event_key, skipped=payload.skipped)
    return StoryAdvanceResponse(
        event_key=payload.event_key,
        xp_awarded=xp,
        story_day=day,
        story_act=act,
    )
