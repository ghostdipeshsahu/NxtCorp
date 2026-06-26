from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # v3.2: provider-neutral LLM env vars. The shim (backend/core/llm.py)
    # prefers these and falls back to the legacy ANTHROPIC_* slots below
    # so old .env files keep working.
    llm_api_key: str = ""
    llm_base_url: str = ""        # blank = default OpenAI endpoint
    llm_model: str = "gpt-4o-mini"

    # Legacy fallbacks — left in place so existing deployments don't break
    # the moment they pull this change. New code should use LLM_* vars.
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    anthropic_model: str = ""

    database_url: str = "postgresql+psycopg2://nxtcorp:nxtcorp@localhost:5432/nxtcorp"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    questions_dir: str = str(Path(__file__).resolve().parent.parent / "questions")
    seed_question_id: str = "p001_detect_capital"

    # Comma-separated list of allowed frontend origins for CORS. In production
    # set this to your deployed Vercel URL(s). Local dev defaults are included.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
