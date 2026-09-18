"""
app/demo
--------
The presentation environment: throwaway Institutional accounts, a
seeded showcase portfolio, and bundled analysis payloads that keep the
app answering when a provider is rate-limited or a key is missing.

Everything here is inert unless `demo_mode` is true in settings. That
switch is separate from `app_env` on purpose, because a demo deployment
is a production deployment in every other respect and handing out free
top-tier accounts must never be a side effect of an environment name.
"""
