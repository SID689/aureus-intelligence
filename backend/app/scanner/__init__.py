"""
app/scanner
-------------
The background market scanner and the Strong Buy leaderboard.

Constants live here, free of imports, so the API layer, the notification
layer and the worker can share them without importing the scoring engine.
"""

HORIZONS: tuple[str, ...] = ("short_term", "medium_term", "long_term")

HORIZON_LABELS: dict[str, str] = {
    "short_term": "Short-term",
    "medium_term": "Medium-term",
    "long_term": "Long-term",
}
