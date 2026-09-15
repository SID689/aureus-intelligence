"""app/scanner/db.py — one connection pool for the scanner, leaderboard and alerts."""

from functools import lru_cache

from sqlalchemy import create_engine

from app.core.config import get_settings


@lru_cache(maxsize=1)
def engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)
