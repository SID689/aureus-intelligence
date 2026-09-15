"""
app/api/v1/metrics.py
----------------------
Exposes a /metrics endpoint in Prometheus text format.
Scraped by Prometheus every 15s (configured in prometheus.yml).

Metrics exposed:
  aureus_analysis_requests_total        counter  {ticker, status}
  aureus_analysis_duration_seconds      histogram {horizon}
  aureus_llm_calls_total                counter  {agent, status}
  aureus_llm_call_duration_seconds      histogram {agent}
  aureus_provider_rate_limit_hits_total counter  {provider}
  aureus_execution_orders_total         counter  {status}
  aureus_ws_connections                 gauge
  aureus_stream_depth                   gauge    {stream}
"""

import logging
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("aureus.metrics")

# Lazy import — prometheus_client only imported if the package is installed
try:
    from prometheus_client import (
        Counter, Histogram, Gauge,
        generate_latest, CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False
    logger.warning("prometheus_client not installed: /metrics will return placeholder")

router = APIRouter(tags=["ops"])

if _PROM_AVAILABLE:
    # ── Metric definitions ─────────────────────────────────────────────────
    ANALYSIS_REQUESTS = Counter(
        "aureus_analysis_requests_total",
        "Total analysis requests processed",
        ["ticker", "status"],
    )
    ANALYSIS_DURATION = Histogram(
        "aureus_analysis_duration_seconds",
        "Full ensemble analysis latency",
        ["horizon"],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
    )
    LLM_CALLS = Counter(
        "aureus_llm_calls_total",
        "Anthropic LLM API calls",
        ["agent", "status"],
    )
    LLM_DURATION = Histogram(
        "aureus_llm_call_duration_seconds",
        "LLM API call latency per agent",
        ["agent"],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
    )
    RATE_LIMIT_HITS = Counter(
        "aureus_provider_rate_limit_hits_total",
        "External API rate limit hits by provider",
        ["provider"],
    )
    EXECUTION_ORDERS = Counter(
        "aureus_execution_orders_total",
        "Execution orders by final status",
        ["status"],
    )
    WS_CONNECTIONS = Gauge(
        "aureus_ws_connections",
        "Active WebSocket connections (alerts + voice)",
    )
    STREAM_DEPTH = Gauge(
        "aureus_stream_depth",
        "Redis Stream message depth",
        ["stream"],
    )

    def record_analysis(ticker: str, status: str, duration: float, horizon: str) -> None:
        ANALYSIS_REQUESTS.labels(ticker=ticker, status=status).inc()
        ANALYSIS_DURATION.labels(horizon=horizon).observe(duration)

    def record_llm_call(agent: str, status: str, duration: float) -> None:
        LLM_CALLS.labels(agent=agent, status=status).inc()
        LLM_DURATION.labels(agent=agent).observe(duration)

    def record_rate_limit(provider: str) -> None:
        RATE_LIMIT_HITS.labels(provider=provider).inc()

    def record_order(status: str) -> None:
        EXECUTION_ORDERS.labels(status=status).inc()

    def set_ws_connections(count: int) -> None:
        WS_CONNECTIONS.set(count)

    def set_stream_depth(stream: str, depth: int) -> None:
        STREAM_DEPTH.labels(stream=stream).set(depth)

else:
    # No-op stubs when prometheus_client isn't installed
    def record_analysis(ticker, status, duration, horizon): pass
    def record_llm_call(agent, status, duration): pass
    def record_rate_limit(provider): pass
    def record_order(status): pass
    def set_ws_connections(count): pass
    def set_stream_depth(stream, depth): pass


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint() -> str:
    """Prometheus scrape endpoint."""
    if not _PROM_AVAILABLE:
        return "# prometheus_client not installed\n"

    # Update live stream depths before generating metrics
    try:
        from app.streaming.redis_streams import stream_lengths
        for stream, depth in stream_lengths().items():
            set_stream_depth(stream, max(0, depth))
    except Exception:
        pass

    # Update WebSocket connection count
    try:
        from app.notifications.websocket_manager import manager
        set_ws_connections(manager.connection_count)
    except Exception:
        pass

    return generate_latest(REGISTRY).decode("utf-8")
