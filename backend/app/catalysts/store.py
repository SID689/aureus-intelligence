"""
app/catalysts/store.py
------------------------
Catalyst persistence. Every write is an idempotent upsert on dedupe_key, so
any source can be re-run at any time without producing duplicates.
"""

import logging
from datetime import date
from functools import lru_cache

from sqlalchemy import create_engine, text

from app.catalysts.models import Catalyst
from app.core.config import get_settings

logger = logging.getLogger("aureus.catalysts.store")


@lru_cache(maxsize=1)
def _engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


_UPSERT = text("""
    INSERT INTO catalysts (dedupe_key, scope, ticker, sector, catalyst_type, title, description,
                           event_date, event_time, date_confirmed, impact, direction,
                           source, source_url, details)
    VALUES (:dedupe_key, :scope, :ticker, :sector, :catalyst_type, :title, :description,
            :event_date, :event_time, :date_confirmed, :impact, :direction,
            :source, :source_url, CAST(:details AS jsonb))
    ON CONFLICT (dedupe_key) DO UPDATE SET
        title          = EXCLUDED.title,
        description    = EXCLUDED.description,
        event_date     = EXCLUDED.event_date,
        event_time     = EXCLUDED.event_time,
        date_confirmed = EXCLUDED.date_confirmed,
        impact         = EXCLUDED.impact,
        direction      = EXCLUDED.direction,
        source_url     = EXCLUDED.source_url,
        details        = EXCLUDED.details,
        updated_at     = now()
    -- Skip no-op rewrites. The market-wide refresh re-ingests thousands of
    -- unchanged rows a day; without this every one of them would churn
    -- updated_at and generate WAL for nothing.
    WHERE (catalysts.title, catalysts.description, catalysts.event_date, catalysts.event_time,
           catalysts.date_confirmed, catalysts.impact, catalysts.direction, catalysts.source_url,
           catalysts.details)
          IS DISTINCT FROM
          (EXCLUDED.title, EXCLUDED.description, EXCLUDED.event_date, EXCLUDED.event_time,
           EXCLUDED.date_confirmed, EXCLUDED.impact, EXCLUDED.direction, EXCLUDED.source_url,
           EXCLUDED.details)
""")

_COLUMNS = """id, dedupe_key, scope, ticker, sector, catalyst_type, title, description,
              event_date, event_time, date_confirmed, impact, direction, source,
              source_url, details, updated_at"""


def upsert(catalysts: list[Catalyst], batch_size: int = 500) -> int:
    """Write catalysts; returns how many distinct rows were submitted."""
    if not catalysts:
        return 0
    rows: dict[str, dict] = {}
    for c in catalysts:
        rows[c.dedupe_key] = c.to_row()  # last one wins within a batch
    payload = list(rows.values())
    with _engine().begin() as conn:
        for i in range(0, len(payload), batch_size):
            conn.execute(_UPSERT, payload[i:i + batch_size])
    return len(payload)


def query_window(ticker: str, sectors: list[str], start: date, end: date) -> list[dict]:
    """A ticker's company catalysts, plus macro events, plus events for its sector."""
    sql = text(f"""
        SELECT {_COLUMNS}
          FROM catalysts
         WHERE event_date BETWEEN :start AND :end
           AND (   (scope = 'company' AND ticker = :ticker)
                OR scope = 'macro'
                OR (scope = 'sector' AND sector = ANY(CAST(:sectors AS text[]))))
         ORDER BY event_date,
                  CASE impact WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
    """)
    with _engine().connect() as conn:
        result = conn.execute(sql, {"ticker": ticker, "sectors": sectors or [], "start": start, "end": end})
        return [dict(r) for r in result.mappings()]


def company_window(tickers: list[str], start: date, end: date) -> list[dict]:
    """Company catalysts for many tickers in one query — the leaderboard's batch path."""
    if not tickers:
        return []
    sql = text(f"""
        SELECT {_COLUMNS}
          FROM catalysts
         WHERE scope = 'company'
           AND ticker = ANY(CAST(:tickers AS text[]))
           AND event_date BETWEEN :start AND :end
    """)
    with _engine().connect() as conn:
        result = conn.execute(sql, {"tickers": tickers, "start": start, "end": end})
        return [dict(r) for r in result.mappings()]


def macro_window(start: date, end: date) -> list[dict]:
    sql = text(f"SELECT {_COLUMNS} FROM catalysts WHERE scope = 'macro' AND event_date BETWEEN :start AND :end ORDER BY event_date")
    with _engine().connect() as conn:
        return [dict(r) for r in conn.execute(sql, {"start": start, "end": end}).mappings()]
