"""
app/quant
-----------
The Advanced Quant Lab: institutional statistical research, relocated out
of the primary three-pillar analysis.

    factors.py         Fama-French 3/5-factor exposures, rolling betas
    risk.py            Monte Carlo, VaR/CVaR, Sharpe/Sortino, beta stability
    mean_reversion.py  z-score deviation, pairs correlation, volatility skew
    lab.py             orchestration for the API

WHY THIS IS A SEPARATE MODULE, NOT A PILLAR

Averaging a factor model against a DCF and an RSI reading produces a
number with no defensible interpretation. Factor exposures, tail risk and
mean-reversion statistics answer research questions — how is this
position's risk decomposed, what does the left tail look like, is this
deviation statistically unusual — and none of those reduce to "is this a
buy". Forcing them into a 0-100 pillar score was the design error this
refactor corrects.

Everything here is computed from price history the platform already
fetches, plus Ken French's factor library, which is free and needs no key.
"""
