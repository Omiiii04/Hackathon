"""
backend/config.py
-----------------
Single source of truth for all configuration.
Reads from the .env file at project root (two levels up from this file).
Every module imports from here — no scattered os.getenv() calls.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of backend/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database — built from individual Postgres vars OR full URL ─────────────
    # Docker-compose uses POSTGRES_* vars; asyncpg uses DATABASE_URL.
    postgres_db:       str = "osint_verify"
    postgres_user:     str = "omii"
    postgres_password: str = "omii00"
    postgres_host:     str = "localhost"
    postgres_port:     int = 5432
    database_url: str = "postgresql://omii:omii00@localhost:5432/osint_verify"
    # Note: if you change POSTGRES_DB in .env, also update DATABASE_URL accordingly.

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── LM Studio (Primary LLM) ───────────────────────────────────────────────
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model:    str = "local-model"
    lm_studio_timeout:  int = 60

    # ── Cloud LLM Fallback ────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model:   str = "gemini-3-flash-preview"

    # ── Data Sources ──────────────────────────────────────────────────────────
    # Wikipedia (no API key — but email REQUIRED by Wikipedia API Terms of Service)
    wikipedia_email: str = "omapar0123@gmail.com"

    # NewsAPI (free tier — 100 req/day)
    news_api_key: str = ""

    # Google Fact Check (optional)
    google_factcheck_api_key: str = ""

    # SERP API (optional)
    serp_api_key: str = ""

    # GDELT (no key — free global news monitoring)
    gdelt_enabled: bool = True

    # DuckDuckGo (no key — HTML scrape)
    ddg_enabled: bool = True

    # Reddit (no key — public JSON API)
    reddit_enabled: bool = True

    # ── Model Paths ───────────────────────────────────────────────────────────
    # BART-MNLI — resolved relative to project root automatically
    bart_model_path: str = str(_PROJECT_ROOT / "models" / "bart_mnli")
    bart_device:     int = -1    # -1 = CPU; 0 = first GPU

    # ── Algorithm ─────────────────────────────────────────────────────────────
    evidence_max_articles:        int   = 5
    evidence_max_sentences:       int   = 5
    early_exit_tier1_threshold:   int   = 2
    early_exit_ratio_high:        float = 0.80
    early_exit_ratio_low:         float = 0.20
    mutation_similarity_threshold: float = 0.75
    confidence_sigmoid_scale:     float = 10.0
    adversarial_paraphrase_threshold: float = 0.70

    # ── Circuit Breakers ──────────────────────────────────────────────────────
    circuit_breaker_fail_max:       int   = 3
    circuit_breaker_reset_seconds:  float = 60.0

    # ── Hardening ─────────────────────────────────────────────────────────────
    http_request_timeout_seconds: int = 8
    gather_timeout_seconds:       int = 20
    freeze_credibility:           bool = False

    # ── App ───────────────────────────────────────────────────────────────────
    secret_key:    str  = "change-me"
    offline_mode:  bool = False
    cache_ttl_days: int = 7

    # ── Celery (derived — not in .env) ────────────────────────────────────────
    @property
    def celery_broker_url(self) -> str:
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        return self.redis_url

    @property
    def wikipedia_user_agent(self) -> str:
        """Standard Wikipedia User-Agent as required by Wikipedia API ToS."""
        return f"OSINT-Verify/1.0 ({self.wikipedia_email})"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings loader — safe to call from anywhere."""
    return Settings()


# Module-level alias for convenient imports:  from config import settings
settings = get_settings()
