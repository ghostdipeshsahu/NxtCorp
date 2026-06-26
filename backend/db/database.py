from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import settings


def _normalize_db_url(url: str) -> str:
    """Render's managed Postgres handsout the deprecated `postgres://` scheme,
    but SQLAlchemy 2.x requires `postgresql+psycopg2://`. Rewrite at engine
    creation time so deployment "just works" without operator intervention.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


_db_url = _normalize_db_url(settings.database_url)

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if _db_url.startswith("sqlite"):
    # FastAPI dispatches handlers on a worker thread pool; sqlite connections
    # must be shareable across threads for that to work.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables, then run idempotent migrations for v3 changes:
       - ALTER players ADD COLUMN progression_phase (TEXT) DEFAULT '1'
       - Backfill SkillScore rows for any (player, skill) missing.
    """
    from backend.db import models  # noqa: F401  (register tables)
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)

    # --- v3 migration: progression_phase column ---
    # Use a single connection to check + add. SQLite + Postgres both support
    # information_schema-ish access; this approach works on both.
    with engine.connect() as conn:
        try:
            cols = conn.execute(text("SELECT progression_phase FROM players LIMIT 1"))
            cols.fetchone()
            # column exists; nothing to do.
        except Exception:
            try:
                conn.execute(text(
                    "ALTER TABLE players ADD COLUMN progression_phase VARCHAR(8) "
                    "NOT NULL DEFAULT '1'"
                ))
                conn.commit()
            except Exception:
                # If even the ALTER fails, the app will still run; missing
                # column will raise on first read, which is fine for dev.
                pass

    # --- v3 migration: attempts.arjun_triggered column ---
    with engine.connect() as conn:
        try:
            cols = conn.execute(text("SELECT arjun_triggered FROM attempts LIMIT 1"))
            cols.fetchone()
        except Exception:
            try:
                conn.execute(text(
                    "ALTER TABLE attempts ADD COLUMN arjun_triggered "
                    "BOOLEAN NOT NULL DEFAULT 0"
                ))
                conn.commit()
            except Exception:
                pass

    # --- v3 migration: players.job_role column ---
    with engine.connect() as conn:
        try:
            cols = conn.execute(text("SELECT job_role FROM players LIMIT 1"))
            cols.fetchone()
        except Exception:
            try:
                conn.execute(text(
                    "ALTER TABLE players ADD COLUMN job_role VARCHAR(32) "
                    "NOT NULL DEFAULT 'software_developer'"
                ))
                conn.commit()
            except Exception:
                pass

    # --- v3 backfill: every player gets a SkillScore row for every skill ---
    from backend.db.models import Player, SkillScore
    from backend.models.schemas import SKILL_KEYS
    with SessionLocal() as db:
        players = db.query(Player).all()
        if not players:
            return
        for p in players:
            existing = {
                s.skill
                for s in db.query(SkillScore)
                .filter(SkillScore.player_id == p.id)
                .all()
            }
            for key in SKILL_KEYS:
                if key not in existing:
                    db.add(SkillScore(player_id=p.id, skill=key, score=0.0))
        db.commit()
