from __future__ import annotations

import logging
import os
import signal
from threading import Event
from typing import Any

from config import WATCHLISTS, WORKER_INTERVAL_SECONDS
from database import (
    connect,
    initialize_database,
    save_forecast,
    save_intelligence_event,
    save_json_signal,
    trim_old_records,
    utc_now,
)
from engine import analyze_market
from forecasting import forecast_price
from intelligence_hub import collect_all
from market_data import get_history
from news_intelligence import get_news_sentiment
from oracle_bot import (
    process_signals,
    risk_exits,
    snapshot,
    update_prices,
)
from oracle_council import deliberate
from opportunity_engine import rank_opportunities
from portfolio_rotation import rotation_plan
from config import OPPORTUNITY_LIMIT
import json


log = logging.getLogger("market-worker")
stop_event = Event()


# =========================================================
# SHUTDOWN HANDLING
# =========================================================


def _request_stop(*_: object) -> None:
    """Request a clean shutdown when Railway stops the service."""
    log.info("Worker shutdown requested.")
    stop_event.set()


signal.signal(signal.SIGTERM, _request_stop)
signal.signal(signal.SIGINT, _request_stop)


# =========================================================
# WORKER STATUS TABLE
# =========================================================


def _ensure_status_table() -> None:
    """Create the worker-status table when it does not exist."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_worker_status (
                market TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                message TEXT,
                last_run TEXT,
                heartbeat TEXT
            )
            """
        )


def set_market_status(
    market: str,
    status: str,
    message: str,
    completed: bool = False,
) -> None:
    """
    Update the dashboard status and worker heartbeat.

    Internal stock trading uses the market name "cash".
    The dashboard displays that worker as "stock".
    """
    now = utc_now()
    status_market = "stock" if market == "cash" else market

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO market_worker_status (
                market,
                status,
                message,
                last_run,
                heartbeat
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (market) DO UPDATE SET
                status = EXCLUDED.status,
                message = EXCLUDED.message,
                heartbeat = EXCLUDED.heartbeat,
                last_run = CASE
                    WHEN %s THEN EXCLUDED.last_run
                    ELSE market_worker_status.last_run
                END
            """,
            (
                status_market,
                status,
                message,
                now if completed else None,
                now,
                completed,
            ),
        )


# =========================================================
# ACTION MESSAGE FORMATTING
# =========================================================


def _format_action(action_record: Any) -> str:
    """
    Convert trade-action records into readable status text.

    risk_exits() and process_signals() may return dictionaries,
    so they must be converted to strings before joining them.
    """
    if not isinstance(action_record, dict):
        return str(action_record)

    action_name = str(
        action_record.get("action", "TRADE")
    ).upper()

    symbol = str(
        action_record.get("symbol", "UNKNOWN")
    ).upper()

    price = action_record.get("price")
    quantity = action_record.get("quantity")
    reason = action_record.get("reason")

    action_text = f"{action_name} {symbol}"

    if quantity is not None:
        try:
            action_text += f" x {float(quantity):,.6f}"
        except (TypeError, ValueError):
            action_text += f" x {quantity}"

    if price is not None:
        try:
            action_text += f" @ ${float(price):,.4f}"
        except (TypeError, ValueError):
            action_text += f" @ {price}"

    if reason:
        action_text += f" ({reason})"

    return action_text


def _build_completion_message(
    label: str,
    actions: list[Any],
) -> str:
    """Build a safe worker status message."""
    message = f"{label} scan completed."

    if not actions:
        return message + " No trades met the rules."

    action_messages = [
        _format_action(action_record)
        for action_record in actions
    ]

    return message + " Actions: " + ", ".join(action_messages)


# =========================================================
# MARKET SCAN
# =========================================================


def scan_market(market: str) -> list[Any]:
    """Scan one market and process simulated trading decisions."""
    watchlist = WATCHLISTS[market]

    signals: list[Any] = []
    prices: dict[str, float] = {}

    for symbol, name in watchlist.items():
        if stop_event.is_set():
            break

        try:
            log.info(
                "Scanning %s symbol %s",
                market,
                symbol,
            )

            hist = get_history(
                symbol,
                "1y",
                "1d",
            )

            if hist is None or hist.empty:
                log.warning(
                    "%s history unavailable for %s",
                    market,
                    symbol,
                )
                continue

            news = get_news_sentiment(
                f"{name} {symbol}"
            )

            sig = analyze_market(
                symbol,
                hist,
                news.sentiment,
            )

            if not sig:
                log.info(
                    "%s produced no signal for %s",
                    market,
                    symbol,
                )
                continue

            council = deliberate(
                sig,
                news.headlines[:8],
            )

            sig.score = council["score"]
            sig.action = council["action"]
            sig.confidence = council["confidence"]

            sig.reason = (
                str(sig.reason)
                + " "
                + str(council["explanation"])
            ).strip()

            signals.append(sig)
            prices[symbol] = float(sig.price)

            save_json_signal(
                market,
                symbol,
                sig.price,
                sig.score,
                sig.action,
                sig.confidence,
                sig.to_dict()
                | {
                    "headlines": news.headlines[:8],
                    "news_source": news.source,
                    "oracle_council": council,
                },
            )

            forecast = forecast_price(
                hist,
                5,
            )

            if forecast:
                save_forecast(
                    market,
                    symbol,
                    forecast,
                )

        except Exception as exc:
            log.exception(
                "%s scan failed for %s: %s",
                market,
                symbol,
                exc,
            )

    ranked = rank_opportunities(signals, OPPORTUNITY_LIMIT)
    if ranked:
        try:
            with connect() as conn:
                now = utc_now()
                for item in ranked:
                    conn.execute("""
                        INSERT INTO opportunity_rankings
                        (market, symbol, rank, opportunity_score, payload, created_at)
                        VALUES (%s,%s,%s,%s,%s::jsonb,%s)
                    """, (market, item["symbol"], item["rank"], item["opportunity_score"], json.dumps(item), now))
        except Exception as exc:
            log.exception("%s opportunity ranking persistence failed: %s", market, exc)
        by_symbol = {item["symbol"]: item for item in ranked}
        signals.sort(key=lambda sig: by_symbol.get(str(getattr(sig,"symbol","")), {}).get("opportunity_score", 0), reverse=True)
        try:
            with connect() as conn:
                positions = list(conn.execute("SELECT symbol, quantity, entry_price, current_price FROM positions WHERE market=%s", (market,)).fetchall())
                enriched = []
                for position in positions:
                    entry = float(position.get("entry_price", 0) or 0)
                    current = float(position.get("current_price", 0) or 0)
                    symbol = str(position.get("symbol", ""))
                    enriched.append({**position, "unrealized_pct": ((current / entry) - 1) * 100 if entry else 0, "opportunity_score": by_symbol.get(symbol, {}).get("opportunity_score", 50)})
                for plan in rotation_plan(enriched, ranked):
                    conn.execute("""INSERT INTO portfolio_rotations
                        (market,sold_symbol,bought_symbol,score_gap,reason,status,created_at)
                        VALUES (%s,%s,%s,%s,%s,'proposed',%s)""",
                        (market,plan["sell_symbol"],plan["buy_symbol"],plan["score_gap"],plan["reason"],utc_now()))
        except Exception as exc:
            log.exception("%s rotation planning failed: %s", market, exc)

    try:
        update_prices(
            market,
            prices,
        )
    except Exception as exc:
        log.exception(
            "%s price update failed: %s",
            market,
            exc,
        )

    actions: list[Any] = []

    try:
        exit_actions = risk_exits(
            market,
            prices,
        )

        if exit_actions:
            actions.extend(exit_actions)

    except Exception as exc:
        log.exception(
            "%s risk exits failed: %s",
            market,
            exc,
        )

    try:
        signal_actions = process_signals(
            market,
            signals,
        )

        if signal_actions:
            actions.extend(signal_actions)

    except Exception as exc:
        log.exception(
            "%s signal processing failed: %s",
            market,
            exc,
        )

    try:
        snapshot(market)

    except Exception as exc:
        log.exception(
            "%s portfolio snapshot failed: %s",
            market,
            exc,
        )

    return actions


# =========================================================
# INTELLIGENCE COLLECTION
# =========================================================


def _collect_stock_intelligence() -> None:
    """
    Run broader intelligence from only the stock worker.

    This prevents the stock and crypto workers from inserting
    the same intelligence events twice.
    """
    try:
        intelligence_results = collect_all()

        for category, result in intelligence_results.items():
            if stop_event.is_set():
                break

            if not result.available:
                continue

            for record in result.records:
                if stop_event.is_set():
                    break

                title = record.get(
                    "title",
                    category,
                )

                save_intelligence_event(
                    category,
                    result.provider,
                    title,
                    record,
                )

        trim_old_records()

    except Exception as exc:
        log.exception(
            "Stock intelligence collection failed: %s",
            exc,
        )


# =========================================================
# WORKER LOOP
# =========================================================


def run_worker(market: str) -> None:
    """Run the requested market worker continuously."""
    requested_market = market.lower().strip()

    if requested_market == "stock":
        market = "cash"
    else:
        market = requested_market

    if market not in WATCHLISTS:
        raise ValueError(
            f"Unknown market: {market}. "
            f"Available markets: {list(WATCHLISTS.keys())}"
        )

    initialize_database()
    from migrations import run_migrations
    run_migrations()
    _ensure_status_table()

    env_name = (
        f"{market.upper()}_WORKER_INTERVAL_SECONDS"
    )

    raw_interval = os.getenv(
        env_name,
        str(WORKER_INTERVAL_SECONDS),
    )

    try:
        interval = max(
            60,
            int(raw_interval),
        )
    except (TypeError, ValueError):
        interval = max(
            60,
            int(WORKER_INTERVAL_SECONDS),
        )

    label = (
        "Stock Market"
        if market == "cash"
        else "Crypto Market"
    )

    log.info(
        "Starting %s worker with %s-second cycles",
        label,
        interval,
    )

    set_market_status(
        market,
        "starting",
        f"{label} worker is starting.",
    )

    while not stop_event.is_set():
        try:
            set_market_status(
                market,
                "running",
                f"{label} worker is scanning.",
            )

            actions = scan_market(market)

            if market == "cash":
                _collect_stock_intelligence()

            message = _build_completion_message(
                label,
                actions,
            )

            set_market_status(
                market,
                "idle",
                message,
                completed=True,
            )

            log.info(message)

        except Exception as exc:
            error_message = (
                f"{label} worker cycle failed: {exc}"
            )

            log.exception(error_message)

            try:
                set_market_status(
                    market,
                    "error",
                    error_message,
                )
            except Exception:
                log.exception(
                    "Could not update worker error status."
                )

        if stop_event.wait(interval):
            break

    stopped_message = (
        f"{label} worker stopped cleanly."
    )

    log.info(stopped_message)

    try:
        set_market_status(
            market,
            "stopped",
            stopped_message,
        )
    except Exception:
        log.exception(
            "Could not update stopped worker status."
        )


# =========================================================
# DIRECT EXECUTION
# =========================================================


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ).upper(),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    selected_market = os.getenv(
        "WORKER_MARKET",
        "cash",
    )

    run_worker(selected_market)