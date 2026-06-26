from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.auth.deps import CurrentPlayer
from backend.auth.routes import router as auth_router
from backend.routes.coffee import router as coffee_router
from backend.routes.onboarding import router as onboarding_router
from backend.routes.story import router as story_router
from backend.routes.task import router as task_router
from backend.db.database import get_db, init_db
from backend.models.schemas import PlayerProfile
from backend.services.profile import build_player_profile


app = FastAPI(title="NxtCorp API", version="0.1.0")

from backend.config import settings as _settings  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(task_router)
app.include_router(coffee_router)
app.include_router(story_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/player/profile", response_model=PlayerProfile)
def get_player_profile(
    player: CurrentPlayer,
    db: Annotated[Session, Depends(get_db)],
) -> PlayerProfile:
    return build_player_profile(db, player)
