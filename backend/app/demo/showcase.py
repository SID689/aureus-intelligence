"""
app/demo/showcase.py
--------------------
What the demo environment is seeded with.

The ticker list is short by design. Every name here has a captured
analysis payload for all three horizons, which is what makes the first
tap instant; a longer list would mean either a slower capture step or
names that fall through to a live pipeline run in front of an audience.

The four were picked to put visibly different verdicts on screen rather
than four variations of the same bullish technology name: a mature
compounder, a momentum semiconductor, a defensive retailer, and a
high-volatility name whose pillars disagree. A demo where everything
reads Strong Buy demonstrates nothing about the scoring.
"""

from typing import Literal

Horizon = Literal["short_term", "medium_term", "long_term"]

HORIZONS: tuple[Horizon, ...] = ("short_term", "medium_term", "long_term")

# Names with bundled payloads. Anything outside this list still works,
# it just runs the live pipeline like any other request.
SHOWCASE_TICKERS: tuple[str, ...] = ("AAPL", "NVDA", "WMT", "TSLA")


class Position:
    """A seeded holding. Cost bases are set well below current prices for
    the long-held names and above for one, so the demo portfolio shows a
    real mix of gains and losses instead of a uniformly green screen."""

    __slots__ = ("ticker", "quantity", "cost_basis")

    def __init__(self, ticker: str, quantity: float, cost_basis: float):
        self.ticker = ticker
        self.quantity = quantity
        self.cost_basis = cost_basis


# ~$250k paper book. Weights are deliberately uneven: an equal-weight
# portfolio makes the concentration and beta readouts say nothing.
SHOWCASE_PORTFOLIO: tuple[Position, ...] = (
    Position("AAPL", 220, 168.40),
    Position("NVDA", 140, 96.25),
    Position("MSFT", 95, 372.10),
    Position("WMT", 310, 71.55),
    Position("JPM", 120, 198.30),
    Position("TSLA", 85, 412.80),
)

SHOWCASE_PORTFOLIO_NAME = "Showcase Book"

DEMO_EMAIL_DOMAIN = "aureus.demo"
DEMO_DISPLAY_NAME = "Demo Analyst"


def is_showcase(ticker: str) -> bool:
    return (ticker or "").upper().strip() in SHOWCASE_TICKERS
