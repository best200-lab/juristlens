"""
config.py — Environment Variables & Settings
All secrets are stored as environment variables on Render
Never hardcode API keys
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Anthropic ──────────────────────────────
    ANTHROPIC_API_KEY: str                        # Set in Render environment variables

    # ── Supabase ───────────────────────────────
    SUPABASE_URL: str                             # Your Supabase project URL
    SUPABASE_SERVICE_KEY: str                     # Supabase service role key (NOT anon key)

    # ── App ────────────────────────────────────
    APP_ENV: str = "production"
    MAX_FILE_SIZE_MB: int = 50                    # Max document size allowed
    MAX_DOCUMENTS_MULTI: int = 20                 # Max docs in multi-review mode

    # ── Claude Model ───────────────────────────
    CLAUDE_MODEL: str = "claude-sonnet-4-6"       # Best model for document analysis

    class Config:
        env_file = ".env"                         # For local development


@lru_cache()
def get_settings() -> Settings:
    return Settings()