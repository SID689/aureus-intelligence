"""
app/sentiment
--------------
The Sentiment pillar's data and NLP layer.

Layout:
    lexicon.py     financial-domain polarity lexicon + phrase patterns
    nlp.py         model layer: FinBERT (opt-in) or lexicon, plus ABSA targeting
    sources.py     news + social ingestion (Finnhub, Yahoo, StockTwits)
    edgar_mdna.py  MD&A tone from the latest 10-K / 10-Q
    engine.py      orchestration: velocity, weighting, 0-100 normalization

The pillar adapter that the ensemble actually calls lives at
app/analysis/sentiment.py, alongside fundamental.py and technical.py.
"""
