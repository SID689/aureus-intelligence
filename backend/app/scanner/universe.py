"""
app/scanner/universe.py
-------------------------
Which stocks the scanner covers: the S&P 500.

Refreshed weekly from Wikipedia's constituents table, which is maintained
within hours of every index change and is what most free tooling uses.
A fetched list only replaces the stored one if it passes sanity checks —
a vandalised or restructured page must not silently shrink the universe to
forty names. If the network or the checks fail, the stored list stands;
if nothing is stored yet, the bundled snapshot seeds it.

The Nasdaq-100 was considered and left out: its Wikipedia table does not
parse reliably, and about 85% of its members are already in the S&P 500.
"""

import io
import json
import logging
import re
from pathlib import Path

from sqlalchemy import text

from app.scanner.db import engine

logger = logging.getLogger("aureus.scanner.universe")

SNAPSHOT_PATH = Path(__file__).with_name("sp500_snapshot.json")
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
INDEX_NAME = "S&P 500"

# The index holds ~503 lines (some companies list two share classes).
_MIN_PLAUSIBLE, _MAX_PLAUSIBLE, _MIN_SECTORS = 480, 520, 10
_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


def load_snapshot() -> tuple[list[dict], str]:
    data = json.loads(SNAPSHOT_PATH.read_text())
    return data["constituents"], data.get("fetched_at", "unknown")


def _fetch_wikipedia() -> list[dict]:
    import httpx
    import pandas as pd

    r = httpx.get(WIKI_URL, timeout=30.0, follow_redirects=True,
                  headers={"User-Agent": "AureusIntelligence/1.0 (market scanner; weekly universe refresh)"})
    r.raise_for_status()
    table = pd.read_html(io.StringIO(r.text), attrs={"id": "constituents"})[0]
    rows: list[dict] = []
    for rec in table.to_dict("records"):
        sym = str(rec.get("Symbol", "")).strip().upper()
        if not _TICKER_RE.match(sym):
            continue
        rows.append({
            "ticker": sym,
            "company_name": str(rec.get("Security", "")).strip() or sym,
            "gics_sector": str(rec.get("GICS Sector", "")).strip() or None,
            "gics_sub_industry": str(rec.get("GICS Sub-Industry", "")).strip() or None,
        })
    return rows


def _problem_with(rows: list[dict]) -> str | None:
    tickers = [r["ticker"] for r in rows]
    if not _MIN_PLAUSIBLE <= len(rows) <= _MAX_PLAUSIBLE:
        return f"{len(rows)} constituents is outside the plausible {_MIN_PLAUSIBLE}-{_MAX_PLAUSIBLE}"
    if len(set(tickers)) != len(tickers):
        return "duplicate tickers"
    sectors = {r["gics_sector"] for r in rows if r["gics_sector"]}
    if len(sectors) < _MIN_SECTORS:
        return f"only {len(sectors)} GICS sectors"
    return None


_UPSERT = text("""
    INSERT INTO scanner_universe (ticker, company_name, gics_sector, gics_sub_industry, indices, active, source, updated_at)
    VALUES (:ticker, :company_name, :gics_sector, :gics_sub_industry, CAST(:indices AS text[]), TRUE, :source, now())
    ON CONFLICT (ticker) DO UPDATE SET
        company_name = EXCLUDED.company_name,
        gics_sector = EXCLUDED.gics_sector,
        gics_sub_industry = EXCLUDED.gics_sub_industry,
        indices = EXCLUDED.indices,
        active = TRUE,
        source = EXCLUDED.source,
        updated_at = now()
""")


def refresh_universe(*, allow_network: bool = True) -> dict:
    if allow_network:
        try:
            rows = _fetch_wikipedia()
            problem = _problem_with(rows)
            if problem is None:
                with engine().begin() as conn:
                    conn.execute(_UPSERT, [{**r, "indices": [INDEX_NAME], "source": "wikipedia"} for r in rows])
                    removed = conn.execute(
                        text("UPDATE scanner_universe SET active = FALSE, updated_at = now() "
                             "WHERE active AND NOT (ticker = ANY(CAST(:t AS text[])))"),
                        {"t": [r["ticker"] for r in rows]},
                    ).rowcount
                logger.info("Scanner universe refreshed", extra={"constituents": len(rows), "removed": removed})
                return {"source": "wikipedia", "constituents": len(rows), "deactivated": removed}
            logger.warning("Rejected fetched constituent list", extra={"problem": problem})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Universe fetch failed; keeping the stored list", extra={"error": str(exc)})

    with engine().begin() as conn:
        stored = conn.execute(text("SELECT count(*) FROM scanner_universe WHERE active")).scalar_one()
        if stored:
            return {"source": "stored", "constituents": stored}
        # Seed only an EMPTY table. A months-old file must never overwrite
        # a newer live list, or re-add a company that has left the index.
        rows, fetched_at = load_snapshot()
        conn.execute(_UPSERT, [{**r, "indices": [INDEX_NAME], "source": f"snapshot:{fetched_at}"} for r in rows])
    logger.info("Scanner universe seeded from snapshot", extra={"constituents": len(rows)})
    return {"source": "snapshot", "constituents": len(rows)}


def active_universe() -> list[dict]:
    sql = text("SELECT ticker, company_name, gics_sector FROM scanner_universe WHERE active ORDER BY ticker")
    with engine().connect() as conn:
        rows = [dict(r) for r in conn.execute(sql).mappings()]
    if rows:
        return rows
    refresh_universe(allow_network=False)
    with engine().connect() as conn:
        return [dict(r) for r in conn.execute(sql).mappings()]
