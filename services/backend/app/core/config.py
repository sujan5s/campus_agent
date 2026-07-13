import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/backend/ directory — DB files and .env live here
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Campus Ops"
    API_V1_STR: str = "/api"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    # --- LLM provider layer (docs/03-TECH-STACK.md) ---
    # Switching provider must ONLY require changing these env vars, never code.
    LLM_PROVIDER: str = "google_genai"  # google_genai | anthropic | openai | ollama
    LLM_MODEL: str = "gemini-2.5-flash"
    GOOGLE_API_KEY: str = ""  # preferred for Gemini
    GEMINI_API_KEY: str = ""  # legacy alias — if GOOGLE_API_KEY is empty, this is used
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # --- Persistence ---
    DATABASE_URL: str = f"sqlite:///{(BACKEND_DIR / 'campus.db').as_posix()}"
    CHECKPOINT_DB: str = str(BACKEND_DIR / "checkpoints.db")

    # --- Auth ---
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # Load from .env file inside services/backend/
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
