from __future__ import annotations

import os
from pathlib import Path

from database import connect, utc_now

TARGET_BALANCE = float(os.getenv("STARTING_BALANCE", "2000"))
MIGRATION_LOCK_ID = 734_202_603

REPAIR_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS opportunity_rankings (
        id BIGSERIAL PRIMARY KEY, market TEXT NOT NULL, symbol TEXT NOT NULL,
        rank INTEGER NOT NULL, opportunity_score DOUBLE PRECISION NOT NULL,
        payload JSONB, created_at TEXT NOT NULL)""",
    """CREATE INDEX IF NOT EXISTS idx_opportunity_market_created
        ON opportunity_rankings(market, created_at DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_opportunity_market_score
        ON opportunity_rankings(market, opportunity_score DESC)""",
    """CREATE TABLE IF NOT EXISTS portfolio_rotations (
        id BIGSERIAL PRIMARY KEY, market TEXT NOT NULL, sold_symbol TEXT,
        bought_symbol TEXT, score_gap DOUBLE PRECISION, reason TEXT,
        status TEXT NOT NULL DEFAULT 'proposed', created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS provider_health (
        provider TEXT PRIMARY KEY, configured BOOLEAN NOT NULL,
        status TEXT NOT NULL, latency_ms DOUBLE PRECISION, message TEXT,
        checked_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS backtest_runs (
        id BIGSERIAL PRIMARY KEY, market TEXT, symbol TEXT NOT NULL,
        strategy TEXT NOT NULL, parameters JSONB, metrics JSONB NOT NULL,
        created_at TEXT NOT NULL)""",
    "ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS peak_equity DOUBLE PRECISION",
    "ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS risk_state TEXT DEFAULT 'normal'",
]


def _repair_database(conn) -> None:
    for statement in REPAIR_STATEMENTS:
        conn.execute(statement)

    # Preserve existing P/L while upgrading legacy portfolios to V3 funding.
    conn.execute(
        """
        UPDATE portfolios
        SET cash = cash + (%s - starting_balance),
            starting_balance = %s,
            peak_equity = GREATEST(COALESCE(peak_equity, 0), %s),
            updated_at = %s
        WHERE starting_balance < %s
        """,
        (TARGET_BALANCE, TARGET_BALANCE, TARGET_BALANCE, utc_now(), TARGET_BALANCE),
    )

    # Normalize the legacy cash heartbeat into the stock worker display name.
    conn.execute(
        """
        INSERT INTO market_worker_status (market,status,message,last_run,heartbeat)
        SELECT 'stock',status,message,last_run,heartbeat
        FROM market_worker_status WHERE market='cash'
        ON CONFLICT (market) DO UPDATE SET
          status=EXCLUDED.status, message=EXCLUDED.message,
          last_run=EXCLUDED.last_run, heartbeat=EXCLUDED.heartbeat
        """
    )
    conn.execute("DELETE FROM market_worker_status WHERE market='cash'")


def run_migrations() -> list[str]:
    """Repair the live schema and apply unapplied SQL files exactly once."""
    folder = Path(__file__).with_name("migrations")
    applied: list[str] = []

    with connect() as conn:
        # All three Railway services may boot together. The transaction-level
        # advisory lock prevents migration races and releases on commit/rollback.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
        _repair_database(conn)

        existing = {
            record["version"]
            for record in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        if not folder.exists():
            return applied

        for path in sorted(folder.glob("*.sql")):
            if path.name in existing:
                continue
            sql = path.read_text(encoding="utf-8").strip()
            if sql:
                conn.execute(sql)
            conn.execute(
                """INSERT INTO schema_migrations(version,applied_at)
                   VALUES (%s,%s) ON CONFLICT(version) DO NOTHING""",
                (path.name, utc_now()),
            )
            applied.append(path.name)

    return applied
