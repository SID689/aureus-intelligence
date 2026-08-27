# Deploying Aureus for free

## What this app actually needs

Measured on the running stack, not estimated:

| Requirement | Figure | Why it constrains hosting |
|---|---|---|
| Memory, all services | **~945 MB** | Rules out 512 MB free tiers |
| Redis commands | **~903,000/day** (~27 M/month) | Rules out every serverless Redis free tier |
| Always-on processes | **3** (worker, agent-worker, beat) | Rules out scale-to-zero platforms |
| Postgres | persistent, with migrations | Rules out ephemeral free databases |

The Redis figure is the one that decides everything. Celery beat fires
tasks every 15s, 30s, 60s and 5min around the clock, and the workers hold
blocking connections. Upstash's free tier is 500,000 commands **per
month** — this stack would exhaust it in about **13 hours**.

That means Redis has to run on a machine you control, which means you
need a VM, which means the "glue together five free PaaS tiers" approach
does not work here. One free VM does.

## Recommended: one Oracle Cloud Always Free VM

Oracle's Always Free tier gives **4 ARM cores, 24 GB RAM, 200 GB
storage**, free indefinitely — not a 12-month trial. It runs this entire
`docker-compose` stack with room to spare.

Honest caveats:

- ARM capacity is frequently unavailable in popular regions. You may see
  "out of host capacity" for days. Retry, or pick a quieter region.
- A credit card is required for identity verification. Stay on Always
  Free shapes and you are not charged.
- Oracle reserves the right to reclaim idle Always Free compute. This app
  is never idle, so in practice that does not bite.

### Steps

1. Create an **Always Free** `VM.Standard.A1.Flex` instance — 4 OCPU,
   24 GB — running Ubuntu 22.04. Open ports 80 and 443 in the VCN
   security list *and* in `iptables` (Oracle images ship a restrictive
   default that catches people out).

2. Install Docker and clone the repo:

```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER
```

3. Fill in `backend/.env` and `frontend/.env.local`. Minimum viable set
   is in "Free-tier keys" below.

4. Bring it up with the production overlay — this is what builds the
   real frontend image rather than the dev server:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

5. Apply the migrations in order:

```bash
for f in db/migrations/*.sql; do docker compose exec -T db psql -U aureus -d aureus_dev -f - < "$f"; done
```

### HTTPS and a hostname, free

A domain name itself is not free (~$10/yr, and worth it). If you want to
spend nothing:

- **Cloudflare Tunnel** — no open inbound ports, free TLS, and it works
  behind Oracle's firewall without touching it. A *named* tunnel needs
  your own domain on Cloudflare; the throwaway `trycloudflare.com`
  hostname changes on every restart, so it is fine for showing someone
  and useless as a real address.
- **DuckDNS + Caddy** — a free stable `yourname.duckdns.org` with
  automatic Let's Encrypt certificates. This is the genuinely-free
  permanent option.

## What is NOT free, and what happens without it

| Service | Free tier | Consequence |
|---|---|---|
| **Anthropic** | none | Reasoning and theses fall back to deterministic text. Verified: `llm_provider` logs "not configured" and returns the template output. Nothing breaks. |
| **Polygon** | 5 req/min, end-of-day | The provider chain falls through to Finnhub then YFinance. Prices work; they are just not real-time. |
| **Finnhub** | 60 req/min | Adequate. |
| **Alpha Vantage** | 25 req/day | Effectively a last-resort fallback only. |
| **SEC EDGAR** | free | Needs a valid `SEC_EDGAR_USER_AGENT` (`Name email@domain.com`) or SEC returns 403. |
| **Stripe** | no monthly fee | Free to run; takes a percentage per transaction. |

So the platform runs end to end on free keys. What you lose is LLM-polished
prose and real-time quotes — not analysis, not scoring, not backtesting.

### Turn the polling down

The beat cadences in `app/workers/celery_app.py` are tuned for local
development. On free API keys they will burn your rate limits for no
benefit — nobody needs the news pipeline sweeping every 15 seconds on a
site with ten visitors. Sensible public values:

| Task | Dev | Suggested |
|---|---|---|
| `preprocess-news` | 15s | 300s |
| `run-agent-pipeline` | 30s | 600s |
| `ingest-news` | 60s | 900s |

That alone cuts Redis traffic and provider calls by more than an order of
magnitude.

## Why not Vercel / Render / Fly

- **Vercel Hobby** is free and excellent for the Next.js half, but its
  terms restrict it to non-commercial personal projects. This app takes
  payments through Stripe. If you split the frontend off, **Cloudflare
  Pages** has no such restriction — though Next.js there needs the
  `next-on-pages` adapter, and NextAuth plus the middleware will need
  work to run on the edge runtime.
- **Render** free web services sleep after 15 minutes idle (~50s cold
  start), offer no free background workers, and delete free Postgres
  databases after 30 days. Three separate blockers.
- **Fly.io** no longer has a genuine free tier.
- **AWS/GCP micro instances** are 1 GB, which is under this stack's
  footprint, and AWS's is 12 months only.

## Before you make it public

- [ ] Generate real `SECRET_KEY` and `NEXTAUTH_SECRET` values
      (`openssl rand -base64 32`). Do not ship the dev ones.
- [ ] Set `NEXTAUTH_URL`, `NEXT_PUBLIC_SITE_URL` and `NEXT_PUBLIC_WS_URL`
      to the public hostname. `NEXT_PUBLIC_*` are inlined **at build
      time**, so they are build args in `Dockerfile.prod`, not runtime
      env — changing them means rebuilding.
- [ ] Delete the `test-institutional@aureus.local` seed account.
- [ ] Point the Stripe webhook at `https://<host>/api/webhooks/stripe`
      and put the new signing secret in `STRIPE_WEBHOOK_SECRET`.
- [ ] Set up `pg_dump` on a cron. Nothing on a free tier is backed up
      for you.
- [ ] The Grafana service in the prod overlay ships default credentials.
      Change them or do not expose that port.
