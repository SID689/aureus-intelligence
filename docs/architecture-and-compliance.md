# Aureus Intelligence — Phase 1
## Architectural Blueprint, Compliance Framework, and Schema Justifications

> **Scope note:** This phase intentionally excludes autonomous agent *trading execution logic* (covered in a later phase). Compliance items below address advisory/disclosure and data-protection obligations only. This document is an engineering checklist, not legal advice — every item under Section 2 needs sign-off from securities and privacy counsel before launch.

---

## 1. High-Level Architectural Blueprint

### 1.1 Dataflow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                │
│   Next.js 15 (App Router, RSC, Server Actions)     Voice Client          │
│   - Dashboard / Portfolio UI                       - WebRTC/WS audio in  │
│   - Auth session (httpOnly cookie)                 - STT (Deepgram/      │
│   - SSE subscriber for live alerts                   Whisper streaming) │
└───────────────┬───────────────────────────────────────────┬──────────────┘
                │ HTTPS REST + SSE                           │ WSS (audio frames
                ▼                                             + control msgs)
┌──────────────────────────────────────────────────────────────────────────┐
│                  API GATEWAY — FastAPI (Uvicorn + Gunicorn workers)       │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  MIDDLEWARE CHAIN (per-request, in order)                         │    │
│  │  1. AuthN — verify JWT / session                                  │    │
│  │  2. Tenant resolution — attach user_id, organization_id           │    │
│  │  3. STRIPE TIER GATEKEEPER — load active subscription_tiers row,  │    │
│  │     reject/degrade request if feature not entitled                │    │
│  │  4. Rate limiter — Redis token bucket keyed by (user_id, route)   │    │
│  │     enforces Sovereign's 10 analysis-requests/day cap             │    │
│  │  5. Audit logger — fire-and-forget write to audit_logs            │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└───────┬───────────────────────┬───────────────────────────┬──────────────┘
        │ sync, low-latency      │ sync, tier-gated           │ enqueue-only
        ▼                       ▼                            ▼
┌───────────────┐      ┌──────────────────┐         ┌──────────────────────┐
│ Read Services  │      │ Voice Gateway     │         │  Redis               │
│ - Portfolio    │      │ - tier minute cap │         │  - Celery broker     │
│   snapshot     │      │   (Elite 500/mo,  │         │  - tier/limit cache  │
│ - Holdings,    │      │    Institutional  │         │  - pub/sub → SSE     │
│   read replica │      │    unthrottled)   │         └──────────┬───────────┘
└───────────────┘      └──────────────────┘                     │
                                                                  ▼
                                  ┌─────────────────────────────────────────────────┐
                                  │     CELERY WORKER POOL (async, queue-isolated)   │
                                  │ ┌───────────────────────────────────────────┐   │
                                  │ │ Queue: market-data                        │   │
                                  │ │  - tick/bar ingestion, beta recalculation  │   │
                                  │ ├───────────────────────────────────────────┤   │
                                  │ │ Queue: news-ingestion                      │   │
                                  │ │  - stream parse → sentiment model →        │   │
                                  │ │    writes news_alerts, portfolio_impacts   │   │
                                  │ ├───────────────────────────────────────────┤   │
                                  │ │ Queue: agent-orchestration (ISOLATED POOL) │   │
                                  │ │  - LangGraph/CrewAI runtime in its own     │   │
                                  │ │    container/process group                │   │
                                  │ │  - NO direct write access to               │   │
                                  │ │    executed_trades; emits proposals to an  │   │
                                  │ │    outbox a separate, deterministic        │   │
                                  │ │    execution service validates and applies │   │
                                  │ └───────────────────────────────────────────┘   │
                                  └──────────────────────┬──────────────────────────┘
                                                           ▼
                                          ┌──────────────────────────────────┐
                                          │   PostgreSQL (primary + replica)  │
                                          │   - RLS enforced per user/org     │
                                          │   - AES-256-GCM credential cols   │
                                          └──────────────────────────────────┘

External integrations (called from the layers above, not shown as boxes
to keep the diagram readable): Stripe (billing webhooks → user_subscriptions),
Alpaca (paper/live execution endpoint), market-data vendor (e.g. Polygon/IEX),
news vendor/stream, KMS (envelope-encryption key operations).
```

### 1.2 Why the layers are split this way

**Sync request path (Next.js → FastAPI) stays thin.** Anything that reads from Postgres or checks a cached tier limit responds in the request/response cycle. Anything that requires LLM inference, news parsing, or multi-step agent reasoning is *never* run inline — it's enqueued and the client is told to subscribe to an SSE channel or poll a job id. This keeps p95 API latency low and means a slow LLM call can't tie up a Uvicorn worker that other tenants' requests need.

**Celery/Redis owns all ingestion.** Market data and news arrive continuously and at a volume that has nothing to do with any single user's request — they belong on a scheduled/streaming worker, not behind a web request. Splitting `market-data` and `news-ingestion` into separate Celery queues means a backlog in one (e.g., a slow news vendor) can't starve the other, and lets Institutional's "sub-second streaming" SLA be met by giving that queue dedicated, higher-priority worker concurrency without touching the market-data queue's configuration.

**The agent orchestrator is isolated, not just async.** LangGraph/CrewAI agents run in their own worker pool/container with its own resource limits and, critically, its own (lack of) database permissions: it can write strategy *state* (`agent_strategies`) but has no grant on `executed_trades`. A separate, deterministic, fully-logged execution service is the only thing with INSERT on `executed_trades`, and it re-validates the proposal against the user's current tier limits and risk configuration before anything reaches a broker. This means a prompt-injection or hallucination inside the orchestrator can corrupt a strategy's *proposed* state but cannot, by construction, place an order — that boundary is enforced by database grants, not just code review. This also de-risks the later "automatic agent trading" phase, since the boundary already exists.

**Stripe gatekeeping lives in middleware, not scattered through business logic.** A single middleware step resolves `user_subscriptions.tier_id → subscription_tiers` (cached in Redis, invalidated by Stripe webhooks on `customer.subscription.updated`) and either rejects, throttles, or annotates the request with entitlements before it reaches any handler. Every downstream service trusts the request context instead of re-querying Stripe or re-deriving tier logic, which is what keeps the three tiers (Sovereign/Elite/Institutional) enforceable from one place instead of N places.

---

## 2. Legal, Regulatory, and Compliance Framework

**This section is a build checklist for engineering and product, not a legal opinion.** Before public launch, retain securities counsel to confirm whether Aureus's specific feature set (especially anything resembling personalized recommendations) triggers Investment Adviser Act registration, and retain privacy counsel to confirm the GDPR/CCPA implementation below is sufficient for your actual data flows and vendor list.

### 2.1 SEC / FINRA Considerations Checklist

- [ ] **Positioning review** — Confirm with counsel whether outputs are "informational/educational" (lower regulatory burden) vs. "personalized investment advice" (triggers Investment Advisers Act of 1940 registration analysis). The schema and UI should make this position consistent everywhere — see disclaimer strings below.
- [ ] **Rule 204-2 recordkeeping readiness** — Every recommendation, alert, or AI-generated output shown to a user must be durably logged with content, timestamp, model version, and the user it was shown to. The `audit_logs` table (category `recommendation` / `disclosure_shown`) is the substrate; pair it with a scheduled export to object-locked (WORM) storage so the "first two years readily accessible, five years total" retention window survives even a database incident.
- [ ] **FINRA Regulatory Notice 17-10 (digital investment advice) themes** — even where Aureus is not itself a broker-dealer, build to this bar: (1) disclosure of algorithm logic and limitations in plain language, (2) testing/validation logged before an algorithm change ships, (3) a documented process for ongoing oversight of model outputs, (4) clear conflict-of-interest disclosure (e.g., if any data vendor relationship could bias output).
- [ ] **Suitability-adjacent guardrails (FINRA Rule 2111 posture)** — even absent formal suitability obligations, capture investor profile signals (`profiles.accredited_investor_self_attested`, risk tolerance fields to be added in a future migration) and refuse to surface leveraged/complex-instrument analysis to users who haven't acknowledged the relevant risk disclosure.
- [ ] **Marketing/performance claims** — any backtest or historical performance figure shown in-product must be paired, in the same view, with the past-performance disclaimer string (below) — never footnoted only.
- [ ] **Change control on model/algorithm versions** — `news_alerts.sentiment_model_version` and an equivalent version field on agent ensembles must be immutable per-row so a regulator (or your own incident review) can reconstruct exactly which model produced a historical output.

### 2.2 Mandatory Disclaimer String Literals

These are meant to be imported as constants and rendered verbatim — never paraphrased per-surface — so legal review only has to happen once per string, not once per screen.

```ts
// shared/compliance/disclaimers.ts
export const SYSTEM_DISCLAIMERS = {
  NOT_FINANCIAL_ADVICE:
    "Aureus Intelligence provides software-generated informational analysis only. " +
    "Nothing presented constitutes investment, legal, or tax advice, nor a recommendation " +
    "to buy, hold, or sell any security. You are solely responsible for your trading and " +
    "investment decisions.",

  PAST_PERFORMANCE:
    "Past performance, backtested results, and historical simulations are not indicative " +
    "of future results. All trading involves risk of loss, including the potential loss " +
    "of principal.",

  UNCERTAINTY_RANGE:
    "All probabilistic outputs (including sentiment scores, confidence values, and " +
    "projected impact ranges) are statistical model estimates with inherent uncertainty " +
    "and should not be interpreted as guarantees of any outcome.",

  SUITABILITY:
    "This platform does not evaluate the suitability of any strategy for your individual " +
    "financial situation, objectives, or risk tolerance. Consult a licensed financial " +
    "advisor before acting on any analysis presented here.",

  PAPER_TRADING_DEFAULT:
    "New accounts and the Sovereign tier operate in simulated (paper) trading mode by " +
    "default. No real capital is at risk unless you explicitly connect and authorize a " +
    "live brokerage account.",

  DATA_DELAY_FREE_TIER:
    "Market data and news on the Sovereign tier may be delayed by 15 minutes or more and " +
    "should not be relied upon for time-sensitive trading decisions.",

  VOICE_RECORDING_CONSENT:
    "Voice sessions are recorded and processed by third-party speech AI providers to " +
    "deliver this feature. Starting a voice session constitutes consent to this " +
    "processing under our Privacy Policy.",

  AI_GENERATED_CONTENT:
    "This content was generated, in whole or in part, by an artificial intelligence " +
    "system and may contain errors or omissions.",
} as const;
```

**Placement rules** (enforce in a shared UI component, not ad hoc):
`NOT_FINANCIAL_ADVICE` — footer of every analysis/agent-output screen.
`PAST_PERFORMANCE` — directly adjacent to any backtest/historical chart, same viewport.
`UNCERTAINTY_RANGE` — inline next to any numeric confidence/sentiment value.
`PAPER_TRADING_DEFAULT` — shown once at brokerage-connection time and persisted via `consent_records`.
`VOICE_RECORDING_CONSENT` — shown before the *first* audio frame is captured each session.

### 2.3 Data Privacy — GDPR / CCPA

- [ ] **Multi-tenant isolation, enforced in the database, not just the app.** Section 3's Row-Level Security policies mean even a query written with a bug (missing `WHERE user_id = ...`) cannot leak cross-tenant rows — Postgres rejects/filters at the row level regardless of application code correctness.
- [ ] **Encryption of brokerage credentials at rest (AES-256-GCM, envelope scheme).** `brokerage_connections` stores ciphertext, a unique 12-byte IV, and the 16-byte GCM auth tag in separate columns — never a single opaque blob — so the auth tag can be verified independently and a reused IV is detectable in code review. The symmetric Data Encryption Key (DEK) is itself wrapped by a KMS-managed Key Encryption Key (KEK); only `kms_key_id` (a reference, not key material) lives in Postgres. This means a database dump or backup leak alone is insufficient to decrypt anything — the KMS must also be compromised.
- [ ] **Data Subject Rights workflow.** `data_subject_requests` tracks GDPR Art. 15/17/20 (access/erasure/portability) and CCPA equivalents with a `received → in_progress → completed` lifecycle and an SLA clock (typically 30 days GDPR / 45 days CCPA — confirm with counsel for your jurisdiction mix).
- [ ] **Consent ledger, not a single boolean.** `consent_records` stores versioned, timestamped consent per type (ToS, privacy policy, voice recording, marketing) so you can prove *which version* a user agreed to and *when* — required to defend a GDPR Art. 7 consent claim.
- [ ] **Breach notification readiness.** GDPR's 72-hour authority-notification clock starts at *awareness*, not confirmation — `audit_logs` with `event_category = 'data_access'` gives you the forensic trail to scope a breach quickly enough to hit that window.
- [ ] **Data residency / sub-processor disclosure.** If any vendor (LLM provider, voice STT/TTS, news vendor) processes EU/UK personal data outside the EEA, confirm SCCs or an adequacy mechanism are in place — this is a contractual/legal item, not a schema item, but it gates which vendors are eligible at all.
- [ ] **CCPA "do not sell/share."** Aureus does not need to build an opt-out mechanism only if it genuinely never sells or shares personal information with third parties for cross-context advertising — confirm this is actually true of every vendor integration (especially ad/analytics SDKs) before relying on that exemption.

---

## 3. Database Schema

Delivered as a separate file: **`schema.sql`** — complete, runnable PostgreSQL 15+ DDL (18 tables, 18 enum types, RLS policies, triggers, and seed data for the three subscription tiers). See inline comments in that file for line-by-line rationale; the design principles are summarized at the top of the file and cross-referenced from Section 1–2 above (e.g., the RLS section directly implements the "multi-tenant isolation" checklist item, and `brokerage_connections`'s three-column credential layout directly implements the AES-256-GCM checklist item).

### Table-to-requirement map

| Requirement from the prompt | Table(s) |
|---|---|
| Users and profile data | `users`, `profiles` |
| Three-tier billing enforcement | `subscription_tiers` (seeded), `user_subscriptions`, `usage_counters` |
| Portfolio state | `portfolios`, `portfolio_holdings` |
| News sentiment + portfolio impact | `news_articles`, `news_alerts`, `portfolio_impacts` |
| Agent strategy state machines + trades | `agent_strategies`, `executed_trades` |
| SEC 204-2 recordkeeping | `audit_logs` |
| GDPR/CCPA consent + DSR | `consent_records`, `data_subject_requests` |
| Voice minute metering | `voice_sessions` |
| Institutional multi-seat tenancy | `organizations` |

Four tables (`organizations`, `usage_counters`, `audit_logs`, `consent_records`, `data_subject_requests`, `voice_sessions`) weren't explicitly named in the prompt but are required to actually *enforce* the tier limits and compliance items the prompt specifies — e.g., you cannot rate-limit Sovereign to 10 requests/day without a counter table, and you cannot demonstrate Rule 204-2 compliance without an append-only log.

---

## 4. Open Items for Phase 2

- Brokerage credential encryption/decryption service (KMS integration, key rotation policy).
- Stripe webhook handler implementation (subscription lifecycle → `user_subscriptions` sync).
- Concrete LangGraph/CrewAI graph definitions and the agent-proposal → execution-service handoff contract.
- Risk-tolerance/investor-profile fields on `profiles` (flagged above, deferred to keep Phase 1 scoped to what was requested).
- Autonomous agent trading compliance (explicitly deferred per your instruction).
