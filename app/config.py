from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agora API"
    database_url: str = (
        "postgresql+asyncpg://agora:agora_dev_password@localhost:5432/agora"
    )
    redis_url: str = "redis://localhost:6379/0"
    backtest_stream: str = "backtest_jobs"
    backtest_consumer_group: str = "backtest_workers"
    backtest_consumer_name: str = "backtest-worker-1"
    backtest_worker_stale_seconds: int = 120
    agent_backtest_timeout_seconds: float = 60.0
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
