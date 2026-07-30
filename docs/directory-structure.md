# Aureus Intelligence — Monorepo Directory Structure

Definitive layout as of Phase 6. Every path below exists in the delivered
codebase; this is not aspirational.

```
aureus-intelligence/
│
├── docker-compose.yml              # dev stack: db, redis, backend, celery×3, frontend
├── docker-compose.prod.yml         # adds prometheus, grafana, exporters, resource limits
│
├── db/
│   └── schema.sql                  # Phase 1 — full Postgres DDL, 18 tables, RLS policies
│
├── docs/
│   ├── architecture-and-compliance.md
│   └── directory-structure.md      # this file
│
├── infrastructure/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/prometheus.yml
│       │   └── dashboards/aureus.yml
│       └── dashboards/aureus.json
│
├── backend/                        # FastAPI + Celery
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py                 # FastAPI app, router registration, lifespan
│       │
│       ├── core/                   # cross-cutting infrastructure
│       │   ├── config.py           # pydantic-settings, single source of env config
│       │   ├── logging_config.py   # structured JSON/dev logging
│       │   └── redis_client.py     # shared Redis connection pool
│       │
│       ├── api/v1/                 # every HTTP + WebSocket route, one file per domain
│       │   ├── analysis.py         #   POST /analysis/run, GET /analysis/result/{id}, /quick/{ticker}
│       │   ├── market.py           #   GET /market/bars/{ticker}, /market/price/{ticker}   [Phase 6]
│       │   ├── portfolio.py        #   CRUD /portfolio/holdings, /portfolio/ensure-default  [Phase 6]
│       │   ├── news.py             #   POST /news/refresh, GET /news/recent, /news/status   [Phase 6]
│       │   ├── backtest.py         #   POST /backtest/run                                   [Phase 6]
│       │   ├── onboarding.py       #   POST /onboarding/complete                            [Phase 6]
│       │   ├── execution.py        #   order submit/approve/reject, account status
│       │   ├── voice.py            #   WS /ws/voice/{user_id}, session info
│       │   ├── ws.py               #   WS /ws/alerts/{user_id}, pending alerts
│       │   ├── billing.py          #   tier-update, payment-failed, auth login/signup/oauth
│       │   └── metrics.py          #   GET /metrics — Prometheus scrape endpoint
│       │
│       ├── ingestion/               # external market/fundamental data providers
│       │   ├── base.py             #   MarketDataProvider / FundamentalDataProvider ABCs
│       │   ├── market_data.py      #   Polygon → AlphaVantage → YFinance, rate-limited + cached
│       │   ├── fundamentals.py     #   Finnhub → SEC EDGAR
│       │   └── rate_limiter.py     #   exponential backoff, RedisTokenBucket
│       │
│       ├── analysis/                # the analytical ensemble engine
│       │   ├── models.py           #   dataclasses: FundamentalScore, TechnicalScore, etc.
│       │   ├── reweighting.py      #   [Phase 6] dynamic weight redistribution — core bug fix
│       │   ├── fundamental.py      #   DCF, safety, growth, moat
│       │   ├── technical.py        #   RSI, MACD, support/resistance, volume
│       │   ├── quantitative.py     #   volatility, alpha/beta, momentum, ridge ML signal
│       │   ├── reasoning.py        #   [Phase 6] deterministic + LLM-polished explanations
│       │   └── ensemble.py         #   top-level aggregation, BUY/HOLD/SELL classification
│       │
│       ├── agents/                  # LangGraph multi-agent news pipeline
│       │   ├── state.py            #   NewsProcessingState TypedDict
│       │   ├── prompts.py          #   per-agent system prompts
│       │   ├── news_analyst.py     #   sentiment + entity extraction node
│       │   ├── risk_delta.py       #   portfolio impact calculation node
│       │   ├── advisory.py         #   alert generation + dispatch node
│       │   ├── graph.py            #   LangGraph state machine wiring
│       │   └── guardrails.py       #   [Phase 6] master system prompt + output validator
│       │
│       ├── streaming/                # Redis Streams ingestion pipeline
│       │   ├── redis_streams.py    #   producer/consumer wrapper, consumer groups
│       │   ├── news_ingestion.py   #   Finnhub poller + RSS poller
│       │   └── preprocessor.py     #   dedup, boilerplate strip, ticker extraction, VADER filter
│       │
│       ├── execution/                # order routing and guardrails
│       │   ├── alpaca_client.py    #   typed wrapper over alpaca-py
│       │   ├── guardrails.py       #   position sizing, tier checks, stop/take-profit
│       │   ├── hitl.py             #   human-in-the-loop approval state machine (HMAC-signed)
│       │   └── order_router.py     #   full proposal → validate → HITL/execute pipeline
│       │
│       ├── voice/                    # conversational voice interface
│       │   ├── session_manager.py  #   Redis-backed conversation memory
│       │   ├── transcription.py    #   Whisper STT + TTS via OpenAI
│       │   └── conversation.py     #   LLM (or rule-based fallback) response generation
│       │
│       ├── notifications/            # alert delivery
│       │   ├── websocket_manager.py
│       │   └── dispatcher.py
│       │
│       ├── billing/
│       │   └── stripe_webhooks.py  #   tier update + downgrade side-effects (pause agents)
│       │
│       ├── backtesting/              # [Phase 6] quantitative validation framework
│       │   ├── metrics.py          #   Sharpe, Sortino, max drawdown, win/loss, custom signal-accuracy metric
│       │   ├── engine.py           #   bar-by-bar replay with explicit look-ahead bias mitigation
│       │   └── run_backtest.py     #   CLI entry point
│       │
│       └── workers/                  # Celery
│           ├── celery_app.py       #   queues, beat schedule, task routing
│           ├── market_tasks.py     #   price/bar refresh
│           ├── news_tasks.py       #   ingest → preprocess → agent pipeline cycles
│           └── analysis_tasks.py   #   async ensemble analysis jobs
│
└── frontend/                       # Next.js 15 App Router
    ├── Dockerfile
    ├── package.json
    ├── next.config.ts              # rewrites /api/v1/* only (not /api/auth or /api/webhooks)
    ├── middleware.ts               # NextAuth + tier-gated route protection
    ├── .env.local.example
    │
    ├── types/
    │   └── index.ts                # shared TS types, TIER_FEATURES map
    │
    ├── lib/
    │   ├── api.ts                  # typed fetch client for every backend endpoint
    │   ├── websocket.ts            # alert stream + voice WebSocket wrappers, browser STT/TTS
    │   ├── auth.ts                 # NextAuth config — credentials + Google OAuth
    │   ├── stripe.ts               # checkout/portal session helpers
    │   └── utils.ts                # cn() class merger
    │
    ├── components/
    │   ├── SessionProvider.tsx
    │   ├── AnalysisPanel.tsx       # ticker analysis UI + reasoning display        [Phase 6 rewrite]
    │   ├── AlertFeed.tsx           # portfolio alerts + general market news tabs   [Phase 6 rewrite]
    │   ├── TradeApproval.tsx       # HITL order approval UI
    │   ├── VoiceInterface.tsx      # push-to-talk voice UI
    │   ├── ui/                     # shadcn-style primitives (button, card, badge)
    │   ├── dashboard/
    │   │   ├── Sidebar.tsx
    │   │   ├── DashboardWidgets.tsx    # MetricCard, SignalBadge, PositionTable
    │   │   └── AddPositionModal.tsx    # [Phase 6] add/merge share positions
    │   ├── charts/
    │   │   ├── PriceChart.tsx      # [Phase 6] REAL OHLCV data (was mock-data in Phase 5)
    │   │   └── PortfolioDonut.tsx
    │   ├── billing/
    │   │   └── UpgradeModal.tsx
    │   └── onboarding/              # [Phase 6]
    │       ├── content.ts          #   the actual educational copy
    │       ├── stateMachine.ts     #   reducer-based wizard state machine
    │       └── OnboardingWizard.tsx
    │
    └── app/
        ├── layout.tsx               # root layout (minimal — chrome lives per route group)
        ├── globals.css
        ├── welcome/page.tsx         # [Phase 6] public landing page
        │
        ├── (auth)/
        │   ├── sign-in/page.tsx     # + Google OAuth button                        [Phase 6]
        │   └── sign-up/page.tsx     # [Phase 6] — previously did not exist
        │
        ├── (onboarding)/
        │   └── onboarding/page.tsx  # [Phase 6] educational wizard entry point
        │
        ├── (dashboard)/             # authenticated shell (Sidebar + top disclaimer bar)
        │   ├── layout.tsx
        │   ├── page.tsx             # main dashboard — real portfolio data           [Phase 6 rewrite]
        │   ├── analysis/page.tsx
        │   ├── orders/page.tsx
        │   └── settings/page.tsx
        │
        ├── voice/page.tsx
        ├── upgrade/page.tsx
        │
        └── api/
            ├── auth/[...nextauth]/route.ts
            ├── webhooks/stripe/route.ts
            └── billing/
                ├── checkout/route.ts    # [Phase 6] — previously referenced but missing
                └── portal/route.ts      # [Phase 6] — previously referenced but missing
```

## Notes on organization decisions

**Why `api/v1/` is flat, not nested by resource.** FastAPI routers are cheap to
split; one file per domain (market, portfolio, news, execution...) keeps each
file under ~200 lines and means you never have to guess which file an endpoint
lives in — the URL prefix tells you.

**Why `analysis/` and `agents/` are separate.** `analysis/` is the synchronous
ensemble engine (fundamental/technical/quantitative scoring) called directly
from API requests. `agents/` is the LangGraph-orchestrated asynchronous news
pipeline. They both use LLMs but serve different request patterns — conflating
them would make the synchronous scoring path depend on graph-execution
machinery it doesn't need.

**No `vector DB / pgvector` directory yet.** The Phase 6 prompt asked for
"vector DB (pgvector/Pinecone) utility locations" — this is listed under Open
Items below because no embedding-based retrieval feature has been specified
yet (there's no RAG use case defined in any phase so far). Once one exists
(e.g., semantic search over historical news, or filing text), the natural
location is `backend/app/vectorstore/` with a `pgvector` migration added to
`db/schema.sql` (requires `CREATE EXTENSION vector;`).

**Migration scripts.** `db/schema.sql` is currently a single monolithic DDL
file applied once. For a production system with a live database that can't be
dropped and recreated, this should become a proper migration tool (Alembic is
the standard choice for a SQLAlchemy-based backend like this one) with
numbered migration files in `backend/migrations/`. Not yet implemented — see
Open Items.
