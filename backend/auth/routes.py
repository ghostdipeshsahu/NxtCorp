from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.security import create_access_token, hash_password, verify_password
from backend.db.database import get_db
from backend.db.models import Player, SkillScore
from backend.models.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from backend.models.schemas import SKILL_KEYS


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    existing = db.query(Player).filter(Player.username == payload.username).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    player = Player(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        avatar_id=payload.avatar_id,
        pronouns=payload.pronouns,
    )
    db.add(player)
    db.flush()  # get id

    for skill in SKILL_KEYS:
        db.add(SkillScore(player_id=player.id, skill=skill, score=0.0))

    db.commit()
    db.refresh(player)

    token = create_access_token(subject=str(player.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    player = db.query(Player).filter(Player.username == payload.username).first()
    if player is None or not verify_password(payload.password, player.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(subject=str(player.id))
    return TokenResponse(access_token=token)
