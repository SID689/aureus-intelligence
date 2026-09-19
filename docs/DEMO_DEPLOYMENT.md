# Putting the demo in front of a room

Two ways to give an audience a link. Pick one.

| | Laptop and a tunnel | Free cloud |
|---|---|---|
| Time to a live URL | about 2 minutes | about 45 minutes, once |
| Cold starts | none | up to 50 seconds after 15 minutes idle |
| Leaderboard, catalysts, news | already full | copied over, see step 4 |
| Survives closing the laptop | no | yes |
| Address | changes every run | permanent |

If the demo is a talk you are giving, use the tunnel. If people need the
link after you leave the room, use the cloud, and read the cold-start
note before you rely on it.

---

## Path A: laptop and a tunnel

One prerequisite:

```bash
brew install cloudflared
```

Then:

```bash
./scripts/demo_up.sh
```

It brings the stack up, seeds the showcase, opens a public HTTPS address,
rewrites `NEXTAUTH_URL` and `NEXT_PUBLIC_SITE_URL` to match it, restarts
the frontend, and prints two links:

```
AUDIENCE LINK     https://<random>.trycloudflare.com/demo
QR CODE SLIDE     https://<random>.trycloudflare.com/demo/qr
```

Open the QR slide on the projector. Ctrl-C stops the tunnel and puts
`frontend/.env.local` back the way it was.

### Why the environment has to be rewritten

NextAuth builds its redirects from `NEXTAUTH_URL`. Left at
`http://localhost:3000`, every phone that signs in gets redirected to its
own localhost and lands nowhere. The script handles it; if you ever open a
tunnel by hand, change that value too.

`NEXT_PUBLIC_WS_URL` is deleted rather than set. Unset means "same origin",
and `next.config.ts` proxies `/api/v1/*` to FastAPI including the
WebSocket upgrade, so live alerts and voice both come through the one
tunnel.

---

## Path B: free cloud

Four services, no card except Render's optional verification:

| Piece | Where | Free tier | What it costs you |
|---|---|---|---|
| Frontend | Vercel Hobby | generous | Hobby is for non-commercial projects. Fine for a demo with billing switched off. |
| API | Render Web Service | 750 hours/month | Sleeps after 15 minutes idle. First request after that takes about 50 seconds. |
| Postgres | Neon | 0.5 GB | None that matters here. |
| Redis | Upstash | 500,000 commands/month | Nothing, as long as you do not run the Celery workers. See "Why no workers". |

### Before any of it: the code has to be on GitHub

Vercel and Render both deploy from a Git repository, and this one has no
remote. Create an empty repository on GitHub, then:

```bash
git remote add origin https://github.com/<you>/aureus-intelligence.git
git push -u origin main
```

Push before you start, because both platforms ask for the repository in
their first screen.

### Why no workers, and why that is fine here

The full stack runs three always-on Celery processes that between them
issue about 900,000 Redis commands a day. That alone rules out every
serverless Redis free tier, which is the argument in
[DEPLOYMENT.md](DEPLOYMENT.md) against gluing free tiers together.

A demo does not need them. The analysis the UI actually calls,
`GET /api/v1/analysis/quick/{ticker}`, runs inline in the web process, and
everything the workers would produce in the background (scanner scores,
the leaderboard, catalysts, the news wire) is copied in at step 4 from a
machine where they have already run. With beat and the workers off, Redis
sees a few thousand commands a day, which fits the free tier with room to
spare.

What you give up: the board stops updating, and the news wire stops
growing. Over a one-hour talk neither is visible.

### 1. Postgres on Neon

1. Create a project at neon.tech. Copy the **pooled** connection string.
2. Apply the schema from your machine:

```bash
./scripts/migrate.sh "postgresql://...neon.tech/neondb?sslmode=require"
```

It runs psql from inside the `postgres:16` container the local stack
already has, so there is no database client to install. Start the stack
first if it is not up (`docker compose up -d db`).

The script runs `db/schema.sql` and then every migration in order, each in
its own psql invocation, which migration 014 requires: it adds a value to
an enum and Postgres refuses that inside a transaction block.

### 2. Redis on Upstash

Create a database at upstash.com and copy the `rediss://` URL. Nothing
else to configure.

### 3. API on Render

The repository has a `render.yaml`, so this is a blueprint rather than a
form:

1. Render dashboard, **New**, **Blueprint**, point it at this repository.
2. It reads `render.yaml` and proposes one free web service.
3. Fill in the values marked `sync: false`, which are the ones Render
   cannot know:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Neon pooled string from step 1 |
| `REDIS_URL` | the Upstash `rediss://` string |
| `SECRET_KEY` | `openssl rand -base64 32` |
| `INTERNAL_API_SECRET` | `openssl rand -base64 32`, kept for step 5 |
| `CORS_ALLOWED_ORIGINS` | your Vercel URL, once you have it in step 5 |
| `SEC_EDGAR_USER_AGENT` | `Your Name your@email.com`, or SEC returns 403 |

Provider keys are all optional. With none of them set the app falls
through to Yahoo for prices and deterministic prose instead of
LLM-written theses. Every endpoint still answers; this was tested with
every key blanked.

Take note of the service URL, `https://aureus-api-xxxx.onrender.com`.

### 4. Fill the database

A fresh Neon database has tables and nothing in them, so the leaderboard
is empty and the catalyst timeline has nothing to draw. Copy the market
data across from your local stack, which has a scanner history:

```bash
./scripts/export_showcase_data.sh showcase_data.sql
./scripts/load_showcase_data.sh "postgresql://...neon.tech/neondb?sslmode=require"
```

The loader prints the row counts on the target when it finishes, so you
can see the board has something to show before you rely on it.

That moves the scanner universe and its snapshots, the leaderboard, the
catalyst calendar, the news wire, sentiment history and the signal
calibration. No accounts, portfolios or consents go with it.

### 5. Frontend on Vercel

1. **New Project**, import the repository, set **Root Directory** to
   `frontend`. Next.js is detected; the defaults are right.
2. Environment variables:

| Variable | Value |
|---|---|
| `NEXTAUTH_URL` | your Vercel URL, `https://<project>.vercel.app` |
| `NEXTAUTH_SECRET` | `openssl rand -base64 32` |
| `NEXTAUTH_API_URL` | the Render URL from step 3 |
| `INTERNAL_API_SECRET` | **the same value as Render's** |
| `NEXT_PUBLIC_DEMO_MODE` | `true` |
| `NEXT_PUBLIC_SITE_URL` | your Vercel URL |
| `NEXT_PUBLIC_WS_URL` | `wss://aureus-api-xxxx.onrender.com` |

`INTERNAL_API_SECRET` must match on both sides exactly. It signs the demo
session call and the realtime tokens; when the two disagree, entering the
demo fails and live alerts close immediately.

`NEXT_PUBLIC_WS_URL` points straight at Render here, unlike the tunnel
path, because Vercel's proxy does not forward WebSocket upgrades to an
external backend.

3. Deploy. Then go back to Render and set `CORS_ALLOWED_ORIGINS` to the
   Vercel URL.

### 6. Warm it up

```bash
curl https://aureus-api-xxxx.onrender.com/health
```

Then open `https://<project>.vercel.app/demo` yourself once. The first
visit provisions and prices the showcase portfolio; every visitor after
that is served from the shared price cache.

### The cold start, plainly

Render's free tier stops the container after 15 minutes without a
request, and the next request waits roughly 50 seconds for it to come
back. In front of an audience that is a long silence.

Two ways around it, in order of preference:

1. Open the URL yourself five minutes before you start, and again during
   the introduction. A service that has been asked for something recently
   stays up.
2. Point a free uptime monitor (UptimeRobot, Better Stack) at
   `/health` every 10 minutes on the day. Turn it off afterwards; a ping
   every 10 minutes all month uses most of the 750 free hours.

---

## The QR code

The app draws its own, at `/demo/qr`, from the address the page was
actually loaded on. Open that page on the machine driving the projector
and the code is always right, including on a tunnel URL that changed five
minutes ago.

It encodes `<your address>/demo`, which signs the visitor straight in.
Dark modules on a bone plate with a four-module quiet zone, which is the
combination that scans reliably off a projector.

If the projected machine reaches the app on an address phones cannot
(localhost during a rehearsal, an internal hostname), the page has a
"Set it" control to type the public address by hand.

---

## The morning of

```bash
docker compose exec -T backend python -m scripts.seed_demo --refresh
```

`--refresh` re-captures the four showcase tickers from live providers, so
the figures on screen are today's, then warms the cache and prints what
the demo has to show:

```
scanner universe                    503
scanner snapshots (verified)       1380
leaderboard entries                 363
catalysts (upcoming)                596
news articles                       784
ready
```

Anything marked THIN is a section of the demo that will look empty.

To clear out accounts from a previous event:

```bash
docker compose exec -T backend python -m scripts.seed_demo --purge
```

Do that **before** the event, never during. Purging deletes the accounts
behind any session a phone is still holding, and those phones then get a
signed-in session pointing at a user that no longer exists.

---

## What demo mode actually changes

Two switches, deliberately separate from `APP_ENV`, so that deploying to
production can never turn this on by accident:

- `DEMO_MODE=true` on the backend enables `POST /api/v1/demo/session`,
  which provisions an account on the Institutional plan without payment.
  It is protected by `INTERNAL_API_SECRET` and is called only by the Next
  server. It also lets the analysis endpoint fall back to the bundled
  snapshots when a provider is unreachable.
- `NEXT_PUBLIC_DEMO_MODE=true` compiles the entry point, the banner and
  the QR page into the frontend. It is inlined at build time, so a demo
  build and a real build are different artefacts.

**Do not set either on a deployment that takes payments.** With both on,
anyone who can reach `/demo` gets a free Institutional account.

Demo accounts are real rows with `auth_provider = 'demo'` and an
`@aureus.demo` address. They cannot be signed into through the login form:
there is no password hash, and the login endpoint refuses an empty one.

---

## If something breaks during the talk

| What you see | What it is | What to do |
|---|---|---|
| "Opening the showcase environment" never finishes | The backend rejected the session call, almost always `INTERNAL_API_SECRET` differing between the two halves | Sign-up still works and the free plan shows the same analysis engine |
| A ticker shows "Captured snapshot" | Providers are unreachable; you are seeing a recorded run of the same engine | Say so. The label is there so you can |
| A ticker returns an error | Not a showcase name and no cached run to fall back to | Use AAPL, NVDA, WMT or TSLA, which always answer |
| The leaderboard is empty | The board only lists verified scores, and a fresh database has none | Step 4 above is what prevents this |
| Live alerts dot is off | The socket is not connected. Nothing else depends on it | Ignore it; the board still loads over REST |
