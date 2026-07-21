from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config import *
from database import connect, row, rows, utc_now
from quant_trade_standard import assess_trade


log = logging.getLogger("oracle-bot")


# =========================================================
# FLEXIBLE TRADING SETTINGS
# =========================================================

FLEXIBLE_COOLDOWN_FACTOR = float(
    globals().get("FLEXIBLE_COOLDOWN_FACTOR", 0.10)
)

HIGH_CONFIDENCE_THRESHOLD = float(
    globals().get("HIGH_CONFIDENCE_THRESHOLD", 0.48)
)

HIGH_SCORE_THRESHOLD = float(
    globals().get("HIGH_SCORE_THRESHOLD", 52.0)
)

EXTRA_OPEN_POSITIONS = int(
    globals().get("EXTRA_OPEN_POSITIONS", 6)
)

MIN_CASH_RESERVE_PCT = float(
    globals().get("MIN_CASH_RESERVE_PCT", 0.01)
)

MIN_TRADE_VALUE = float(
    globals().get("MIN_TRADE_VALUE", 1.00)
)

MAX_TRADE_VALUE_PCT = float(
    globals().get("MAX_TRADE_VALUE_PCT", 0.35)
)

DEFAULT_STOP_LOSS_PCT = float(
    globals().get("STOP_LOSS_PCT", 0.06)
)

DEFAULT_TAKE_PROFIT_PCT = float(
    globals().get("TAKE_PROFIT_PCT", 0.10)
)

DEFAULT_TRAILING_STOP_PCT = float(
    globals().get("TRAILING_STOP_PCT", 0.045)
)

DEFAULT_COOLDOWN_MINUTES = int(
    globals().get("TRADE_COOLDOWN_MINUTES", 15)
)

DEFAULT_MAX_OPEN_POSITIONS = int(
    globals().get("MAX_OPEN_POSITIONS", 14)
)

STARTING_BALANCE_VALUE = float(
    globals().get("STARTING_BALANCE", 200.0)
)


# =========================================================
# BASIC HELPERS
# =========================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)
        if result != result:
            return default
        return result
    except (TypeError, ValueError):
        return default


def safe_text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default
    return str(value).strip()


def signal_value(
    signal: Any,
    name: str,
    default: Any = None,
) -> Any:
    if signal is None:
        return default

    if isinstance(signal, dict):
        return signal.get(name, default)

    return getattr(signal, name, default)


def normalized_score(signal: Any) -> float:
    score = safe_float(signal_value(signal, "score", 0.0))

    if score <= 1.0:
        score *= 100.0

    return max(0.0, min(100.0, score))


def normalized_confidence(signal: Any) -> float:
    confidence = safe_float(
        signal_value(signal, "confidence", 0.0)
    )

    if confidence > 1.0:
        confidence /= 100.0

    return max(0.0, min(1.0, confidence))


def signal_action(signal: Any) -> str:
    return safe_text(
        signal_value(signal, "action", "HOLD"),
        "HOLD",
    ).upper()


def signal_price(
    signal: Any,
    fallback: float = 0.0,
) -> float:
    for field in (
        "price",
        "current_price",
        "close",
        "last_price",
        "spot",
    ):
        value = safe_float(signal_value(signal, field, 0.0))
        if value > 0:
            return value

    return fallback


def execute(
    sql: str,
    params: tuple[Any, ...] = (),
) -> None:
    with connect() as conn:
        conn.execute(sql, params)


# =========================================================
# DATABASE COMPATIBILITY
# =========================================================

def _table_columns(
    table_name: str,
) -> set[str]:
    try:
        records = rows(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )

        return {
            safe_text(record.get("column_name"))
            for record in records
            if record.get("column_name")
        }

    except Exception:
        return set()


def _insert_compatible(
    table_name: str,
    values: dict[str, Any],
) -> bool:
    columns = _table_columns(table_name)

    if not columns:
        return False

    usable = {
        key: value
        for key, value in values.items()
        if key in columns
    }

    if not usable:
        return False

    names = list(usable)
    placeholders = ", ".join(["%s"] * len(names))
    sql_columns = ", ".join(names)

    try:
        execute(
            f"""
            INSERT INTO {table_name}
            ({sql_columns})
            VALUES ({placeholders})
            """,
            tuple(usable[name] for name in names),
        )
        return True

    except Exception:
        log.exception("Unable to insert into %s", table_name)
        return False


# =========================================================
# PORTFOLIO
# =========================================================

def ensure_portfolio(
    market: str,
) -> dict[str, Any]:
    market = safe_text(market).lower()

    existing = row(
        """
        SELECT *
        FROM portfolios
        WHERE market = %s
        """,
        (market,),
    )

    if existing:
        return existing

    now = utc_now()

    try:
        execute(
            """
            INSERT INTO portfolios
            (
                market,
                cash,
                starting_balance,
                updated_at
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (market) DO NOTHING
            """,
            (
                market,
                STARTING_BALANCE_VALUE,
                STARTING_BALANCE_VALUE,
                now,
            ),
        )

    except Exception:
        log.exception(
            "Could not initialize portfolio for %s",
            market,
        )

    return (
        row(
            """
            SELECT *
            FROM portfolios
            WHERE market = %s
            """,
            (market,),
        )
        or {
            "market": market,
            "cash": STARTING_BALANCE_VALUE,
            "starting_balance": STARTING_BALANCE_VALUE,
        }
    )


def portfolio_equity(
    market: str,
) -> dict[str, float]:
    portfolio = ensure_portfolio(market)

    positions = rows(
        """
        SELECT *
        FROM positions
        WHERE market = %s
        """,
        (market,),
    )

    positions_value = sum(
        safe_float(position.get("quantity"))
        * safe_float(
            position.get(
                "current_price",
                position.get(
                    "price",
                    position.get("average_price", 0.0),
                ),
            )
        )
        for position in positions
    )

    cash = safe_float(
        portfolio.get("cash"),
        STARTING_BALANCE_VALUE,
    )

    starting_balance = safe_float(
        portfolio.get("starting_balance"),
        STARTING_BALANCE_VALUE,
    )

    return {
        "cash": cash,
        "positions_value": positions_value,
        "equity": cash + positions_value,
        "starting_balance": starting_balance,
    }


def recent_trade(
    market: str,
    symbol: str,
) -> dict[str, Any] | None:
    cooldown_minutes = max(
        1,
        int(DEFAULT_COOLDOWN_MINUTES * FLEXIBLE_COOLDOWN_FACTOR),
    )

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(minutes=cooldown_minutes)
    ).isoformat()

    try:
        return row(
            """
            SELECT *
            FROM trades
            WHERE market = %s
              AND symbol = %s
              AND created_at >= %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                market,
                symbol,
                cutoff,
            ),
        )
    except Exception:
        return None


# =========================================================
# PRICE UPDATES
# =========================================================

def update_prices(
    market: str,
    prices: dict[str, float] | None = None,
    *_: Any,
    **__: Any,
) -> int:
    market = safe_text(market).lower()
    prices = prices or {}

    updated = 0

    positions = rows(
        """
        SELECT *
        FROM positions
        WHERE market = %s
        """,
        (market,),
    )

    for position in positions:
        symbol = safe_text(position.get("symbol")).upper()
        current_price = safe_float(
            prices.get(symbol, prices.get(symbol.lower()))
        )

        if current_price <= 0:
            continue

        try:
            execute(
                """
                UPDATE positions
                SET current_price = %s,
                    highest_price = GREATEST(
                        COALESCE(highest_price, %s),
                        %s
                    ),
                    updated_at = %s
                WHERE market = %s
                  AND symbol = %s
                """,
                (
                    current_price,
                    current_price,
                    current_price,
                    utc_now(),
                    market,
                    symbol,
                ),
            )
            updated += 1

        except Exception:
            log.exception(
                "Price update failed for %s %s",
                market,
                symbol,
            )

    return updated


# =========================================================
# POSITION CLOSING
# =========================================================

def _close_position(
    market: str,
    position: dict[str, Any],
    price: float,
    reason: str,
) -> bool:
    market = safe_text(market).lower()
    symbol = safe_text(position.get("symbol")).upper()
    quantity = safe_float(position.get("quantity"))
    price = safe_float(price)

    if not symbol or quantity <= 0 or price <= 0:
        return False

    value = quantity * price

    entry_price = safe_float(
        position.get(
            "average_price",
            position.get("entry_price", price),
        ),
        price,
    )

    realized_pnl = (price - entry_price) * quantity
    now = utc_now()

    try:
        with connect() as conn:
            portfolio = conn.execute(
                """
                SELECT *
                FROM portfolios
                WHERE market = %s
                FOR UPDATE
                """,
                (market,),
            ).fetchone()

            if not portfolio:
                return False

            new_cash = safe_float(portfolio.get("cash")) + value

            conn.execute(
                """
                UPDATE portfolios
                SET cash = %s,
                    updated_at = %s
                WHERE market = %s
                """,
                (
                    new_cash,
                    now,
                    market,
                ),
            )

            conn.execute(
                """
                DELETE FROM positions
                WHERE market = %s
                  AND symbol = %s
                """,
                (
                    market,
                    symbol,
                ),
            )

            conn.execute(
                """
                INSERT INTO trades (
                    market,
                    symbol,
                    side,
                    quantity,
                    price,
                    value,
                    realized_pnl,
                    score,
                    reason,
                    created_at
                )
                VALUES (
                    %s, %s, 'SELL', %s, %s, %s,
                    %s, NULL, %s, %s
                )
                """,
                (
                    market,
                    symbol,
                    quantity,
                    price,
                    value,
                    realized_pnl,
                    reason,
                    now,
                ),
            )

        log.info(
            "%s SELL %s quantity=%.8f price=%.6f reason=%s",
            market.upper(),
            symbol,
            quantity,
            price,
            reason,
        )
        return True

    except Exception:
        log.exception(
            "Could not close %s %s",
            market,
            symbol,
        )
        return False


# =========================================================
# RISK EXITS
# =========================================================

def risk_exits(
    market: str,
    prices: dict[str, float] | None = None,
    *_: Any,
    **__: Any,
) -> list[dict[str, Any]]:
    market = safe_text(market).lower()
    prices = prices or {}

    actions: list[dict[str, Any]] = []

    positions = rows(
        """
        SELECT *
        FROM positions
        WHERE market = %s
        """,
        (market,),
    )

    for position in positions:
        symbol = safe_text(position.get("symbol")).upper()

        entry_price = safe_float(
            position.get(
                "average_price",
                position.get("entry_price", 0.0),
            )
        )

        current_price = safe_float(
            prices.get(symbol, prices.get(symbol.lower()))
        )

        if current_price <= 0:
            current_price = safe_float(
                position.get("current_price", 0.0)
            )

        highest_price = safe_float(
            position.get("highest_price"),
            max(entry_price, current_price),
        )

        if entry_price <= 0 or current_price <= 0:
            continue

        change_pct = (
            current_price - entry_price
        ) / entry_price

        trailing_change = (
            (current_price - highest_price) / highest_price
            if highest_price > 0
            else 0.0
        )

        reason: str | None = None

        if change_pct <= -DEFAULT_STOP_LOSS_PCT:
            reason = "stop_loss"
        elif change_pct >= DEFAULT_TAKE_PROFIT_PCT:
            reason = "take_profit"
        elif (
            highest_price > entry_price
            and trailing_change <= -DEFAULT_TRAILING_STOP_PCT
        ):
            reason = "trailing_stop"

        if not reason:
            continue

        if _close_position(
            market,
            position,
            current_price,
            reason,
        ):
            actions.append(
                {
                    "market": market,
                    "symbol": symbol,
                    "action": "SELL",
                    "price": current_price,
                    "reason": reason,
                    "return_pct": change_pct,
                }
            )

    return actions


# =========================================================
# POSITION COUNT
# =========================================================

def _open_position_count(
    market: str,
) -> int:
    try:
        result = row(
            """
            SELECT COUNT(*) AS total
            FROM positions
            WHERE market = %s
            """,
            (market,),
        )

        return int(safe_float(result.get("total"))) if result else 0

    except Exception:
        return 0


# =========================================================
# BUY EXECUTION
# =========================================================

def _buy(
    market: str,
    symbol: str,
    price: float,
    signal: Any,
    quant_assessment: Any | None = None,
) -> tuple[bool, str]:
    """Execute an aggressive simulated buy and return (success, reason)."""
    market = safe_text(market).lower()
    symbol = safe_text(symbol).upper()
    price = safe_float(price)

    if not market:
        return False, "missing market"
    if not symbol:
        return False, "missing symbol"
    if price <= 0:
        return False, f"invalid price={price}"

    equity_data = portfolio_equity(market)
    cash = safe_float(equity_data.get("cash"), STARTING_BALANCE_VALUE)
    equity = max(
        safe_float(equity_data.get("equity"), STARTING_BALANCE_VALUE),
        0.01,
    )

    cash_reserve = max(
        STARTING_BALANCE_VALUE * MIN_CASH_RESERVE_PCT,
        equity * MIN_CASH_RESERVE_PCT,
    )
    available_cash = max(0.0, cash - cash_reserve)

    if available_cash < MIN_TRADE_VALUE:
        return (
            False,
            f"insufficient available cash={available_cash:.2f}; "
            f"reserve={cash_reserve:.2f}",
        )

    maximum_trade_value = min(
        available_cash,
        equity * MAX_TRADE_VALUE_PCT,
    )

    confidence = normalized_confidence(signal)
    score = normalized_score(signal)

    # Accepted signals get a meaningful allocation while stronger signals
    # receive more capital.
    strength = max(
        0.55,
        min(1.0, max(confidence, score / 100.0)),
    )

    quant_multiplier = safe_float(
        getattr(quant_assessment, "position_multiplier", 1.0),
        1.0,
    ) if quant_assessment is not None else 1.0

    trade_value = min(
        maximum_trade_value * strength * quant_multiplier,
        available_cash,
    )

    if trade_value < MIN_TRADE_VALUE:
        return (
            False,
            f"trade value too small={trade_value:.2f}; "
            f"minimum={MIN_TRADE_VALUE:.2f}",
        )

    quantity = trade_value / price
    if quantity <= 0:
        return False, f"invalid quantity={quantity}"

    now = utc_now()

    try:
        with connect() as conn:
            portfolio_record = conn.execute(
                """
                SELECT *
                FROM portfolios
                WHERE market = %s
                FOR UPDATE
                """,
                (market,),
            ).fetchone()

            if not portfolio_record:
                return False, "portfolio row missing"

            current_cash = safe_float(
                portfolio_record.get("cash"),
                cash,
            )
            current_available_cash = max(
                0.0,
                current_cash - cash_reserve,
            )
            trade_value = min(
                trade_value,
                current_available_cash,
            )

            if trade_value < MIN_TRADE_VALUE:
                return (
                    False,
                    f"cash changed during execution; "
                    f"available={current_available_cash:.2f}",
                )

            quantity = trade_value / price
            new_cash = current_cash - trade_value

            existing = conn.execute(
                """
                SELECT *
                FROM positions
                WHERE market = %s
                  AND symbol = %s
                FOR UPDATE
                """,
                (market, symbol),
            ).fetchone()

            if existing:
                old_quantity = safe_float(existing.get("quantity"))
                old_average = safe_float(
                    existing.get(
                        "average_price",
                        existing.get("entry_price", price),
                    ),
                    price,
                )
                combined_quantity = old_quantity + quantity

                if combined_quantity <= 0:
                    return False, "combined position quantity is invalid"

                combined_average = (
                    (old_quantity * old_average)
                    + (quantity * price)
                ) / combined_quantity

                old_highest = safe_float(
                    existing.get("highest_price"),
                    price,
                )

                conn.execute(
                    """
                    UPDATE positions
                    SET quantity = %s,
                        entry_price = %s,
                        average_price = %s,
                        current_price = %s,
                        highest_price = %s,
                        updated_at = %s
                    WHERE market = %s
                      AND symbol = %s
                    """,
                    (
                        combined_quantity,
                        combined_average,
                        combined_average,
                        price,
                        max(old_highest, price),
                        now,
                        market,
                        symbol,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO positions (
                        market,
                        symbol,
                        quantity,
                        entry_price,
                        average_price,
                        current_price,
                        highest_price,
                        opened_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    """,
                    (
                        market,
                        symbol,
                        quantity,
                        price,
                        price,
                        price,
                        price,
                        now,
                        now,
                    ),
                )

            conn.execute(
                """
                UPDATE portfolios
                SET cash = %s,
                    updated_at = %s
                WHERE market = %s
                """,
                (new_cash, now, market),
            )

            conn.execute(
                """
                INSERT INTO trades (
                    market,
                    symbol,
                    side,
                    quantity,
                    price,
                    value,
                    realized_pnl,
                    score,
                    reason,
                    created_at
                )
                VALUES (
                    %s, %s, 'BUY', %s, %s, %s,
                    0, %s, %s, %s
                )
                """,
                (
                    market,
                    symbol,
                    quantity,
                    price,
                    trade_value,
                    score,
                    (
                        f"Quant-approved buy; score={score:.2f}; "
                        f"confidence={confidence:.2f}; "
                        f"{getattr(quant_assessment, 'reason', 'legacy standard')}"
                    ),
                    now,
                ),
            )

        log.info(
            "%s | BUY EXECUTED | %s | quantity=%.8f | "
            "price=%.6f | value=%.2f | score=%.2f | confidence=%.3f",
            market.upper(),
            symbol,
            quantity,
            price,
            trade_value,
            score,
            confidence,
        )
        return True, "buy executed"

    except Exception as exc:
        log.exception(
            "%s | BUY FAILED | %s",
            market.upper(),
            symbol,
        )
        return False, f"database execution error: {exc}"


# =========================================================
# SIGNAL PROCESSING
# =========================================================

def process_signals(
    market: str,
    signals: list[Any] | tuple[Any, ...] | None,
    prices: dict[str, float] | None = None,
    *_: Any,
    **__: Any,
) -> list[dict[str, Any]]:
    market = safe_text(market).lower()
    signals = list(signals or [])
    prices = prices or {}
    actions: list[dict[str, Any]] = []

    maximum_positions = (
        DEFAULT_MAX_OPEN_POSITIONS
        + EXTRA_OPEN_POSITIONS
    )

    log.info(
        "%s | Processing %d signals | max_positions=%d | "
        "score_threshold=%.1f | confidence_threshold=%.2f",
        market.upper(),
        len(signals),
        maximum_positions,
        HIGH_SCORE_THRESHOLD,
        HIGH_CONFIDENCE_THRESHOLD,
    )

    for signal in signals:
        symbol = safe_text(signal_value(signal, "symbol", "")).upper()
        if not symbol:
            log.info("%s | REJECT | missing symbol", market.upper())
            continue

        action = signal_action(signal)
        score = normalized_score(signal)
        confidence = normalized_confidence(signal)
        price = signal_price(
            signal,
            safe_float(prices.get(symbol, prices.get(symbol.lower()))),
        )

        log.info(
            "%s | CANDIDATE | %s | action=%s | score=%.2f | "
            "confidence=%.3f | price=%.6f",
            market.upper(),
            symbol,
            action,
            score,
            confidence,
            price,
        )

        if price <= 0:
            log.info(
                "%s | REJECT | %s | invalid/missing price",
                market.upper(),
                symbol,
            )
            continue

        if action in {"SELL", "EXIT", "CLOSE"}:
            position = row(
                """
                SELECT *
                FROM positions
                WHERE market = %s
                  AND symbol = %s
                """,
                (market, symbol),
            )

            if not position:
                log.info(
                    "%s | REJECT SELL | %s | no open position",
                    market.upper(),
                    symbol,
                )
                continue

            if _close_position(market, position, price, "sell_signal"):
                actions.append(
                    {
                        "market": market,
                        "symbol": symbol,
                        "action": "SELL",
                        "price": price,
                        "reason": "sell_signal",
                    }
                )
            continue

        buy_signal = action in {
            "BUY",
            "STRONG_BUY",
            "ACCUMULATE",
            "LONG",
        }

        # Strong HOLD signals can become accumulation entries.
        aggressive_hold = (
            action == "HOLD"
            and score >= max(50.0, HIGH_SCORE_THRESHOLD - 2.0)
            and confidence >= max(
                0.44,
                HIGH_CONFIDENCE_THRESHOLD - 0.04,
            )
        )

        if not buy_signal and not aggressive_hold:
            log.info(
                "%s | REJECT | %s | action=%s is not an entry",
                market.upper(),
                symbol,
                action,
            )
            continue

        # A BUY qualifies through either score or confidence. Only signals
        # that are weak on both measurements are rejected.
        minimum_score = max(45.0, HIGH_SCORE_THRESHOLD - 7.0)
        minimum_confidence = max(
            0.40,
            HIGH_CONFIDENCE_THRESHOLD - 0.08,
        )

        if score < minimum_score and confidence < minimum_confidence:
            log.info(
                "%s | REJECT | %s | weak signal: score=%.2f < %.2f "
                "and confidence=%.3f < %.3f",
                market.upper(),
                symbol,
                score,
                minimum_score,
                confidence,
                minimum_confidence,
            )
            continue

        quant_assessment = None
        if ENABLE_QUANT_TRADE_STANDARD:
            quant_assessment = assess_trade(
                signal,
                market=market,
                min_quality=QUANT_MIN_QUALITY,
                min_net_ev_pct=QUANT_MIN_NET_EV_PCT,
                max_spread_pct=QUANT_MAX_SPREAD_PCT,
                max_slippage_pct=QUANT_MAX_SLIPPAGE_PCT,
            )
            if not quant_assessment.approved:
                log.info(
                    "%s | QUANT REJECT | %s | %s",
                    market.upper(),
                    symbol,
                    quant_assessment.reason,
                )
                continue

        existing_position = row(
            """
            SELECT *
            FROM positions
            WHERE market = %s
              AND symbol = %s
            """,
            (market, symbol),
        )

        open_count = _open_position_count(market)
        if not existing_position and open_count >= maximum_positions:
            log.info(
                "%s | REJECT | %s | position limit reached %d/%d",
                market.upper(),
                symbol,
                open_count,
                maximum_positions,
            )
            continue

        recent = recent_trade(market, symbol)
        if recent:
            log.info(
                "%s | REJECT | %s | cooldown active after recent trade",
                market.upper(),
                symbol,
            )
            continue

        success, reason = _buy(market, symbol, price, signal, quant_assessment)
        if not success:
            log.info(
                "%s | REJECT BUY | %s | %s",
                market.upper(),
                symbol,
                reason,
            )
            continue

        actions.append(
            {
                "market": market,
                "symbol": symbol,
                "action": "BUY",
                "price": price,
                "score": score,
                "confidence": confidence,
                "reason": reason,
                "quant": quant_assessment.to_dict() if quant_assessment else None,
            }
        )

    log.info(
        "%s | Signal processing complete | executed_actions=%d",
        market.upper(),
        len(actions),
    )
    return actions


# =========================================================
# EQUITY SNAPSHOT
# =========================================================

def snapshot(
    market: str,
    *_: Any,
    **__: Any,
) -> dict[str, float]:
    market = safe_text(market).lower()
    data = portfolio_equity(market)

    equity = safe_float(data.get("equity"))
    cash = safe_float(data.get("cash"))
    positions_value = safe_float(
        data.get("positions_value")
    )
    starting_balance = max(
        safe_float(
            data.get("starting_balance"),
            STARTING_BALANCE_VALUE,
        ),
        0.01,
    )

    drawdown = min(
        0.0,
        (equity - starting_balance) / starting_balance,
    )

    try:
        execute(
            """
            INSERT INTO equity_snapshots (
                market,
                equity,
                cash,
                positions_value,
                drawdown,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                market,
                equity,
                cash,
                positions_value,
                drawdown,
                utc_now(),
            ),
        )
    except Exception:
        log.exception(
            "Could not save equity snapshot for %s",
            market,
        )

    return {
        "cash": cash,
        "positions_value": positions_value,
        "equity": equity,
        "starting_balance": starting_balance,
        "drawdown": drawdown,
    }
