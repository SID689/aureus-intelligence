# Deploying Aureus for free

> Putting the app in front of an audience for a presentation is a
> different problem with a different answer: see
> [DEMO_DEPLOYMENT.md](DEMO_DEPLOYMENT.md). A demo runs without the Celery
> workers, which is what makes the free PaaS tiers ruled out below viable
> for that case and only that case.

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

Leave `scan-market-every-15min` alone. It fires every 15 minutes but the
scanner decides for itself whether a pass is due (every 15 minutes while
the US market is open, hourly otherwise), and its provider spend is capped
in `app/scanner/budget.py` regardless of how often beat fires.

## Market scanner, catalysts and alerts

### What it spends

The scanner holds itself to ceilings sized for free plans, leaving the
larger share of each quota to people using the site:

| Provider | Free limit | Scanner ceiling | Worst case per day |
|---|---|---|---|
| Finnhub | 60/min, shared with users | 30/min | ~2,200 calls |
| StockTwits | ~200/hour per IP | 90/hour | ~1,300 calls |
| Yahoo (prices) | unpublished | ~6 batch requests per pass | ~260 requests |
| SEC EDGAR | 10/sec | a few per minute | ~650 requests |

The daily catalyst sweep (10:30 UTC) adds about 25 Finnhub calendar calls.
On a shared or tightly limited key, set `SCANNER_ENABLED=false` in
`backend/.env` and the rest of the platform runs without it.

Coverage builds over the first day: prices for the whole index on the
first pass, fundamentals and sentiment a few dozen names per pass. The
board stays empty until scores are verified, by design.

### Web Push

1. Generate a VAPID key pair once per environment and put it in
   `backend/.env`. Never reuse the development keys, and never rotate them
   casually: every existing browser subscription is bound to the public key
   and silently stops working when it changes.

```bash
docker compose exec -T backend python -c "from py_vapid import Vapid01; import base64; from cryptography.hazmat.primitives import serialization as s; v=Vapid01(); v.generate_keys(); e=lambda b: base64.urlsafe_b64encode(b).rstrip(b'=').decode(); print('VAPID_PUBLIC_KEY='+e(v.public_key.public_bytes(s.Encoding.X962, s.PublicFormat.UncompressedPoint))); print('VAPID_PRIVATE_KEY='+e(v.private_key.private_numbers().private_value.to_bytes(32,'big')))"
```

2. Set `VAPID_CLAIM_SUB=mailto:<a real address you read>`. Push services
   use it to contact you before they block a sender.

3. Push only works on HTTPS (browsers exempt `localhost` alone), so it
   will not work over a bare IP.

4. `pywebpush` is in `requirements.txt`. Rebuild the backend images after
   pulling this change, or the alert worker fails at import:

```bash
docker compose build backend celery-worker celery-agent-worker celery-beat
```

### WebSockets behind a proxy

Live alerts use `/api/v1/ws/market`. Set `NEXT_PUBLIC_WS_URL` to
`wss://<host>` (a build arg, like the other `NEXT_PUBLIC_*` values) and
make sure the proxy forwards the upgrade. Caddy does this by default;
nginx needs `proxy_http_version 1.1` plus the `Upgrade` and `Connection`
headers on that location.

### Not covered on free data

Economic releases (CPI, payrolls) are not on the catalyst timeline:
Finnhub's economic calendar is a paid endpoint and the BLS prohibits
automated retrieval of its schedule. FOMC dates, earnings, SEC 8-K events,
dividends and FDA advisory meetings are covered. The timeline itself tells
users what is missing and why.

## Never run `next build` inside the dev container

`docker-compose.yml` mounts `.next` as an anonymous volume:

```
volumes:
  - ./frontend:/app
  - /app/node_modules
  - /app/.next
```

That volume is the dev server's working directory. Running
`docker compose exec frontend npx next build` overwrites it with a
PRODUCTION build — `BUILD_ID`, `prerender-manifest.json`, production
chunk names — and the dev server then 404s on every one of its own
chunks. Every page serves a broken shell, and because the volume is
anonymous it survives `docker compose restart`, so the obvious fix does
not work.

To test that the app builds for production, build the image, which uses
its own filesystem and never touches the running dev volume:

```bash
docker build -f frontend/Dockerfile.prod -t aureus-frontend-prod frontend
```

If it has already happened, clear the volume's CONTENTS — the directory
itself is a mount point and cannot be removed:

```bash
docker compose exec -T frontend sh -c 'rm -rf /app/.next/* /app/.next/.[!.]*' && docker compose restart frontend
```

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
- [ ] Generate production VAPID keys and set a real `VAPID_CLAIM_SUB`
      (see "Web Push" above). The development claim address is a
      placeholder at `example.invalid`.
- [ ] `INTERNAL_API_SECRET` must be identical in `backend/.env` and
      `frontend/.env.local`. The leaderboard, notifications and live
      alerts authenticate with tokens signed by it, and fail closed
      (401/503) when the two disagree or it is unset.
- [ ] Confirm the proxy passes WebSocket upgrades for `/api/v1/ws/`.
- [ ] Have counsel complete and review the Terms of Service and Privacy
      Policy. The legal entity name, registered address, governing law and
      arbitration seat are bracketed placeholders in `frontend/lib/legal.ts`,
      and the contact addresses there assume the `aureusintelligence.com`
      domain. The pages state that the company is not a registered
      investment adviser; confirm that is true before publishing it.
- [ ] Deleting an account is handled by email today (the Privacy Policy
      promises deletion or de-identification within 30 days). Put an owner
      and a process behind that promise before launch.
- [ ] `DEMO_MODE` and `NEXT_PUBLIC_DEMO_MODE` must both be false or unset.
      Together they let anyone who reaches `/demo` provision a free
      Institutional account, which is correct for a presentation host and
      catastrophic for one taking payments. `docker compose exec -T backend
      python -m scripts.seed_demo --purge` clears any accounts a demo left
      behind.
- [ ] Create the $12/month Plus price in Stripe and set `STRIPE_PRICE_PLUS`
      in `frontend/.env.local` beside the Elite and Institutional prices.
      Until it is set, choosing Plus returns a clear "no price configured"
      error instead of opening checkout. Migration `014_plus_tier.sql` adds
      the plan itself.
