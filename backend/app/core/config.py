from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    DATABASE_URL: str
    REDIS_URL: str 

    AUTO_CREATE_TABLES: bool = False
    SQLALCHEMY_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Keep the API key optional so unrelated app startup paths
    # do not fail before the LLM feature is actually invoked.
    LLM_API_KEY: str | None = None
    LLM_API_URL: str
    LLM_MODEL: str

    REDIS_CONVERSATION_TTL: int = 60 * 60 * 24 * 7
    REDIS_DESTINATION_CACHE_TTL: int = 60 * 60 * 24

    @field_validator(
        "DATABASE_POOL_SIZE",
        "DATABASE_MAX_OVERFLOW",
        "REDIS_CONVERSATION_TTL",
        "REDIS_DESTINATION_CACHE_TTL",
    )
    @classmethod
    def validate_non_negative_ints(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be >= 0")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Compatibility exports for the existing codebase.
DATABASE_URL = settings.DATABASE_URL
REDIS_URL = settings.REDIS_URL
AUTO_CREATE_TABLES = settings.AUTO_CREATE_TABLES
SQLALCHEMY_ECHO = settings.SQLALCHEMY_ECHO
DATABASE_POOL_SIZE = settings.DATABASE_POOL_SIZE
DATABASE_MAX_OVERFLOW = settings.DATABASE_MAX_OVERFLOW
LLM_API_KEY = settings.LLM_API_KEY
LLM_API_URL = settings.LLM_API_URL
LLM_MODEL = settings.LLM_MODEL
