from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    database_path: str = "data/estatebot.db"
    index_path: str = "data/index"
    raw_snapshot_dir: str = "data/raw"
    seed_corpus_path: str = "data/seed_corpus.json"
    seed_on_empty: bool = True
    log_level: str = "INFO"
    cors_allowed_origins: str = "http://localhost:8000,http://localhost:5173"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_primary: str = "google/gemma-4-31b-it:free"
    openrouter_model_fallback_1: str | None = "z-ai/glm-5.2:free"
    openrouter_model_fallback_2: str | None = "minimax/minimax-m3:free"
    openrouter_selectable_models: str = (
        "dots-studio/dots-3-note-preview:free,"
        "nvidia/nemotron-3-ultra-550b-a55b:free,"
        "nvidia/nemotron-3-super-120b-a12b:free,"
        "google/gemma-4-31b-it:free,"
        "z-ai/glm-5.2:free,"
        "minimax/minimax-m3:free"
    )
    openrouter_http_referer: str = "http://localhost:8000"
    openrouter_app_title: str = "EstateBot"

    retrieval_mode: Literal["hybrid", "vector_only", "bm25_only"] = "bm25_only"
    max_retrieval_chunks: int = Field(default=8, ge=1, le=20)
    chat_history_turns: int = Field(default=8, ge=0, le=20)
    chat_max_message_chars: int = Field(default=2000, ge=100, le=10000)
    chat_rate_limit_requests: int = Field(default=20, ge=1)
    chat_rate_limit_window_seconds: int = Field(default=300, ge=1)
    llm_attempt_timeout_seconds: float = 20
    llm_total_timeout_seconds: float = 45
    llm_max_tokens: int = 800

    scraper_user_agent: str = "EstateBot-Assignment-Scraper/1.0 (+https://example.com; educational use)"
    scrape_delay_seconds: float = 2
    scrape_connect_timeout_seconds: float = 10
    scrape_read_timeout_seconds: float = 20
    scrape_max_retries: int = 3
    max_darglobal_press: int = 25
    max_wasalt_listings: int = 400
    max_pages_per_category: int = 5
    scrape_cache_enabled: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_allowed_origins.split(",") if x.strip()]

    @property
    def models(self) -> list[str]:
        return [x for x in [self.openrouter_model_primary, self.openrouter_model_fallback_1, self.openrouter_model_fallback_2] if x]

    @property
    def selectable_models(self) -> list[str]:
        return list(dict.fromkeys(x.strip() for x in self.openrouter_selectable_models.split(",") if x.strip()))


@lru_cache
def get_settings() -> Settings:
    return Settings()
