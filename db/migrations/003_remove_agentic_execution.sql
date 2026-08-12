-- Migration 003: remove agentic live-trading execution subsystem
--
-- Aureus previously included an autonomous-agent live-brokerage-execution
-- feature: agent_strategies (strategy state machine), executed_trades
-- (broker order audit trail), and brokerage_connections (encrypted Alpaca
-- API credentials), fronted by app/execution/*.py (guardrails, HITL
-- approval, order routing, Alpaca client) and a POST /api/v1/execution/*
-- API. That feature is deprecated and fully removed from the codebase in
-- favor of a user-facing historical Strategy Backtesting Engine
-- (see app/backtesting/) — no live orders are ever submitted to a broker
-- anymore. This migration drops the now-orphaned tables/columns/enums.
--
-- Safe to run on a database where these tables are empty or contain only
-- test data. If you have real historical trade records you want to keep
-- for reference, export executed_trades before running this (see the
-- commented COPY statement below).
--
-- Run this once against your database:
--   docker compose exec db psql -U aureus -d aureus_dev -f /path/to/003_remove_agentic_execution.sql
-- or paste its contents into a psql session.

-- Optional: uncomment to archive existing rows to CSV before dropping.
-- \copy (SELECT * FROM executed_trades) TO '/tmp/executed_trades_archive.csv' WITH CSV HEADER;
-- \copy (SELECT * FROM agent_strategies) TO '/tmp/agent_strategies_archive.csv' WITH CSV HEADER;

BEGIN;

-- RLS policies on the tables being dropped (must go before DROP TABLE,
-- though PostgreSQL would also drop them implicitly with the table).
DROP POLICY IF EXISTS tenant_isolation_brokerage_connections ON brokerage_connections;
DROP POLICY IF EXISTS tenant_isolation_agent_strategies       ON agent_strategies;
DROP POLICY IF EXISTS tenant_isolation_executed_trades        ON executed_trades;

-- executed_trades references agent_strategies and brokerage_connections;
-- drop it first.
DROP TABLE IF EXISTS executed_trades;
DROP TABLE IF EXISTS agent_strategies;

-- portfolios.brokerage_connection_id references brokerage_connections —
-- drop the column before the table it points to.
ALTER TABLE portfolios DROP COLUMN IF EXISTS brokerage_connection_id;
DROP TABLE IF EXISTS brokerage_connections;

-- Tier feature flags that only the deleted execution/guardrails.py read.
-- supports_human_in_loop_alerts is INTENTIONALLY KEPT — it's still read
-- by app/agents/risk_delta.py to flag significant NEWS impacts for human
-- review, an unrelated feature that predates and survives this removal.
ALTER TABLE subscription_tiers DROP COLUMN IF EXISTS supports_live_execution;
ALTER TABLE subscription_tiers DROP COLUMN IF EXISTS concurrent_agent_strategies_limit;

-- Enum types that only the dropped tables/columns used.
DROP TYPE IF EXISTS broker_provider;
DROP TYPE IF EXISTS connection_status;
DROP TYPE IF EXISTS agent_type;
DROP TYPE IF EXISTS agent_strategy_status;
DROP TYPE IF EXISTS trade_side;
DROP TYPE IF EXISTS order_type;
DROP TYPE IF EXISTS trade_status;

COMMIT;
