import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_str_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default

DATABASE_URL = _get_str_env(
    "DATABASE_URL",
    "postgresql://postgres:ngandb@localhost:5432/travel_db"
)

REDIS_URL = _get_str_env(
    "REDIS_URL",
    "redis://localhost:6379/0"
)

AUTO_CREATE_TABLES = _get_bool_env("AUTO_CREATE_TABLES", default=True)
SQLALCHEMY_ECHO = _get_bool_env("SQLALCHEMY_ECHO", default=False)
DATABASE_POOL_SIZE = _get_int_env("DATABASE_POOL_SIZE", 10)
DATABASE_MAX_OVERFLOW = _get_int_env("DATABASE_MAX_OVERFLOW", 20)
