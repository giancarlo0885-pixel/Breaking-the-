from __future__ import annotations

import html
import json
import textwrap
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from backtesting import run_backtest
from cache import stats as cache_stats
from config import APP_NAME, STARTING_BALANCE
from dashboard_helpers import (
    action_class,
    as_float,
    clean_market,
    normalized_confidence,
    parse_json,
    short_reason,
    star_rating,
    worker_is_online,
)
from database import initialize_database, row, rows
from market_data import get_history
from migrations import run_migrations
from provider_diagnostics import provider_diagnostics


st.set_page_config(
    page_title=f"{APP_NAME} — Oracle Home",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .stApp {
        background:
          radial-gradient(circle at 8% 0%, rgba(0,210,160,.13), transparent 28%),
          radial-gradient(circle at 96% 3%, rgba(125,70,255,.16), transparent 30%),
          #080c12;
      }
      .block-container {max-width: 1450px; padding-top: .8rem; padding-bottom: 2.5rem;}
      .hero {padding: 22px; border: 1px solid #273344; border-radius: 24px; background: rgba(15,21,30,.95); margin-bottom: 14px;}
      .hero h1 {margin: 0; font-size: clamp(2rem, 6vw, 3.1rem); line-height: 1.05;}
      .hero p {color: #aab5c5; margin: .55rem 0 0; font-size: 1rem;}
      .section-label {color:#aab5c5; text-transform:uppercase; letter-spacing:.14em; font-size:.74rem; font-weight:800; margin-bottom:.35rem;}
      .decision-card {padding: 22px; border: 1px solid #273344; border-radius: 22px; background: linear-gradient(145deg,#111a26,#0c121b); min-height: 230px;}
      .decision-symbol {font-size: clamp(2.2rem, 8vw, 4.4rem); font-weight: 900; line-height: 1; margin:.25rem 0 .6rem;}
      .pill {display:inline-block; padding:.38rem .72rem; border-radius:999px; font-weight:850; margin-right:.35rem; margin-bottom:.35rem;}
      .buy {background:rgba(44,205,121,.17); color:#55e59a; border:1px solid rgba(85,229,154,.35);}
      .hold {background:rgba(255,190,70,.14); color:#ffc65c; border:1px solid rgba(255,198,92,.35);}
      .sell {background:rgba(255,80,95,.14); color:#ff7480; border:1px solid rgba(255,116,128,.35);}
      .muted {color:#9ba8ba;}
      .metric-card {padding:18px; border:1px solid #273344; border-radius:18px; background:#0f151e; min-height:150px;}
      .metric-card .name {color:#aab5c5; font-size:.9rem;}
      .metric-card .value {font-size:2.25rem; font-weight:850; margin:.25rem 0;}
      .metric-card .delta-up {color:#50db8d; font-weight:800;}
      .metric-card .delta-down {color:#ff6d77; font-weight:800;}
      .opp-card {padding:16px; border:1px solid #273344; border-radius:18px; background:#0f151e; margin-bottom:10px;}
      .opp-rank {font-size:.74rem; color:#8f9bad; font-weight:800; letter-spacing:.11em;}
      .opp-symbol {font-size:1.42rem; font-weight:900; margin:.15rem 0;}
      .stars {color:#ffd166; letter-spacing:.06em;}
      .worker-card {padding:17px; border:1px solid #273344; border-radius:18px; background:#0f151e; min-height:160px;}
      .status-dot {display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;}
      .online {background:#50db8d;box-shadow:0 0 12px rgba(80,219,141,.65)}
      .offline {background:#ff6d77;}
      .vote-row {padding:12px 14px;border:1px solid #263140;border-radius:14px;background:#0f151e;margin-bottom:8px;}
      .decision-list {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:12px;}
      .decision-item {border:1px solid #273344;border-radius:18px;background:#0f151e;padding:17px;min-width:0;box-shadow:0 8px 24px rgba(0,0,0,.18);}
      .decision-top {display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;}
      .decision-name {font-size:1.25rem;font-weight:900;letter-spacing:.01em;}
      .decision-meta {display:flex;gap:8px;flex-wrap:wrap;color:#9ba8ba;font-size:.84rem;margin-bottom:10px;}
      .decision-score {display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;}
      .decision-stat {background:#0b1119;border:1px solid #222d3b;border-radius:12px;padding:10px;}
      .decision-stat small {display:block;color:#8f9bad;margin-bottom:3px;}
      .decision-stat b {font-size:1.05rem;}
      .decision-reason {color:#c2ccda;line-height:1.5;font-size:.94rem;margin-top:11px;}
      .decision-summary {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0 16px;}
      .summary-box {border:1px solid #273344;border-radius:16px;background:#0f151e;padding:15px;}
      .summary-box small {display:block;color:#95a2b4;margin-bottom:4px;}
      .summary-box b {font-size:1.45rem;}
      .plain-note {border-left:4px solid #7d6cff;background:#101722;padding:12px 14px;border-radius:12px;color:#c7d1df;margin:8px 0 14px;}
      div[data-testid="stMetric"] {border:1px solid #273344;border-radius:16px;padding:12px;background:#0f151e;}
      div[data-testid="stTabs"] button {font-size:.95rem;}
      @media (max-width: 1100px) {
        .decision-list {grid-template-columns:repeat(2,minmax(0,1fr));}
      }
      @media (max-width: 700px) {
        .decision-list {grid-template-columns:1fr;}
        .decision-summary {grid-template-columns:1fr;}
      }
      @media (max-width: 700px) {
        .block-container {padding-left:.75rem;padding-right:.75rem;}
        .hero {padding:18px;}
        .hero h1 {font-size:2rem;}
        .decision-card {min-height:0;padding:18px;}
        .metric-card .value {font-size:1.9rem;}
        .decision-item {padding:14px;border-radius:16px;}
        .decision-name {font-size:1.15rem;}
        .decision-top {align-items:flex-start;}
        div[data-testid="stTabs"] {overflow-x:auto;}
        div[data-testid="stTabs"] [role="tablist"] {min-width:max-content;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def bootstrap() -> list[str]:
    initialize_database()
    return run_migrations()




def render_html(markup: str) -> None:
    """Render indented multiline HTML without Markdown turning it into a code block."""
    cleaned = textwrap.dedent(markup).strip()
    st.markdown(cleaned, unsafe_allow_html=True)


def money(value: Any) -> str:
    return f"${as_float(value):,.2f}"


def pct(value: Any) -> str:
    number = as_float(value)
    return f"{number:+.2f}%"


def safe_rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    try:
        return rows(query, params)
    except Exception:
        return []


def market_summary(market: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, float]]:
    portfolio = row("SELECT * FROM portfolios WHERE market=%s", (market,)) or {}
    positions = safe_rows("SELECT * FROM positions WHERE market=%s ORDER BY symbol", (market,))
    positions_value = sum(as_float(x.get("quantity")) * as_float(x.get("current_price")) for x in positions)
    cash = as_float(portfolio.get("cash"), float(STARTING_BALANCE))
    start = as_float(portfolio.get("starting_balance"), float(STARTING_BALANCE))
    equity = cash + positions_value
    return portfolio, positions, {
        "cash": cash,
        "positions_value": positions_value,
        "equity": equity,
        "return_pct": ((equity / start) - 1) * 100 if start else 0.0,
    }


def latest_signal() -> dict[str, Any]:
    records = safe_rows(
        """
        SELECT market,symbol,score,action,confidence,details,created_at
        FROM signals
        ORDER BY id DESC
        LIMIT 50
        """
    )
    if not records:
        return {}
    buy_records = [x for x in records if str(x.get("action", "")).upper() == "BUY"]
    candidates = buy_records or records
    return max(
        candidates,
        key=lambda x: normalized_confidence(x.get("confidence")) + as_float(x.get("score")),
    )


def latest_opportunities(limit: int = 5) -> list[dict[str, Any]]:
    records = safe_rows(
        """
        SELECT DISTINCT ON (market, symbol)
            market,symbol,rank,opportunity_score,payload,created_at
        FROM opportunity_rankings
        ORDER BY market,symbol,created_at DESC
        """
    )
    return sorted(records, key=lambda x: as_float(x.get("opportunity_score")), reverse=True)[:limit]


def trade_reason(signal: dict[str, Any]) -> str:
    details = parse_json(signal.get("details"))
    for key in ("explanation", "reason", "summary"):
        if details.get(key):
            return str(details[key])
    score = as_float(signal.get("score"))
    confidence = normalized_confidence(signal.get("confidence"))
    return f"Council score {score:.1f} with {confidence:.0f}% confidence based on trend, momentum, catalysts, liquidity, and risk."


def render_portfolio_card(title: str, icon: str, data: dict[str, float]) -> None:
    delta_class = "delta-up" if data["return_pct"] >= 0 else "delta-down"
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="name">{icon} {html.escape(title)}</div>
          <div class="value">{money(data['equity'])}</div>
          <div class="{delta_class}">{pct(data['return_pct'])}</div>
          <div class="muted">Cash {money(data['cash'])} · Invested {money(data['positions_value'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_worker(label: str, icon: str, record: dict[str, Any]) -> None:
    status = str(record.get("status", "waiting")).lower()
    online = worker_is_online(status)
    status_text = "ONLINE" if online else status.upper() or "WAITING"
    message = html.escape(str(record.get("message") or "No completed scan yet."))
    heartbeat = html.escape(str(record.get("heartbeat") or "—"))
    st.markdown(
        f"""
        <div class="worker-card">
          <div class="section-label">{icon} {html.escape(label)}</div>
          <h3><span class="status-dot {'online' if online else 'offline'}"></span>{status_text}</h3>
          <div class="muted">{message}</div>
          <div class="muted" style="margin-top:.65rem;font-size:.8rem">Heartbeat: {heartbeat}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


try:
    applied_migrations = bootstrap()
    database_error = None
except Exception as exc:
    applied_migrations = []
    database_error = str(exc)

st.markdown(
    f"""
    <div class="hero">
      <h1>🔮 {html.escape(APP_NAME)}</h1>
      <p>Simple Oracle Home · Council V3 · $2,000 stock vs $2,000 crypto · paper trading</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if database_error:
    st.error(f"PostgreSQL connection required: {database_error}")
    st.stop()

_, stock_positions, stock = market_summary("cash")
_, crypto_positions, crypto = market_summary("crypto")
statuses = safe_rows("SELECT * FROM market_worker_status ORDER BY market")
workers_by_market = {clean_market(x.get("market")): x for x in statuses}
workers_online = sum(worker_is_online(x.get("status")) for x in workers_by_market.values() if clean_market(x.get("market")) in {"stock", "crypto"})

home, portfolio_tab, council_tab, radar_tab, journal_tab, backtest_tab, system_tab = st.tabs(
    ["🏠 Home", "💼 Portfolio", "👥 Council", "📡 Radar", "📓 Journal", "🧪 Backtest", "⚙️ System"]
)

with home:
    signal = latest_signal()
    opportunities = latest_opportunities(5)
    best_opp = opportunities[0] if opportunities else {}
    symbol = str(best_opp.get("symbol") or signal.get("symbol") or "SCANNING")
    action = str(signal.get("action") or parse_json(best_opp.get("payload")).get("action") or "HOLD").upper()
    confidence = normalized_confidence(signal.get("confidence") or parse_json(best_opp.get("payload")).get("confidence"))
    opportunity_score = as_float(best_opp.get("opportunity_score"), as_float(signal.get("score")))
    reason = short_reason(best_opp) if best_opp else trade_reason(signal) if signal else "Workers are scanning the market for the next high-quality setup."

    left, right = st.columns([1.15, .85])
    with left:
        st.markdown(
            f"""
            <div class="decision-card">
              <div class="section-label">Oracle decision</div>
              <span class="pill {action_class(action)}">{html.escape(action)}</span>
              <span class="pill hold">{confidence:.0f}% confidence</span>
              <div class="decision-symbol">{html.escape(symbol)}</div>
              <div class="stars">{star_rating(opportunity_score)} &nbsp; Opportunity score {opportunity_score:.1f}</div>
              <p class="muted" style="font-size:1.02rem;line-height:1.55">{html.escape(reason)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="section-label">Council snapshot</div>', unsafe_allow_html=True)
        latest_signals = safe_rows("SELECT action FROM signals ORDER BY id DESC LIMIT 24")
        buy_votes = sum(str(x.get("action", "")).upper() == "BUY" for x in latest_signals)
        hold_votes = sum(str(x.get("action", "")).upper() == "HOLD" for x in latest_signals)
        sell_votes = sum(str(x.get("action", "")).upper() == "SELL" for x in latest_signals)
        st.metric("Recent Council Signals", len(latest_signals))
        c1, c2, c3 = st.columns(3)
        c1.metric("Buy", buy_votes)
        c2.metric("Hold", hold_votes)
        c3.metric("Sell", sell_votes)
        st.caption("These are the latest recorded symbol decisions, not a guarantee of future returns.")

    st.markdown("### 💰 Portfolio scoreboard")
    p1, p2, p3 = st.columns(3)
    with p1:
        render_portfolio_card("Stock Portfolio", "📈", stock)
    with p2:
        render_portfolio_card("Crypto Portfolio", "₿", crypto)
    with p3:
        combined = stock["equity"] + crypto["equity"]
        combined_start = float(STARTING_BALANCE) * 2
        combined_return = ((combined / combined_start) - 1) * 100 if combined_start else 0
        render_portfolio_card("Combined Capital", "🏦", {"equity": combined, "cash": stock["cash"] + crypto["cash"], "positions_value": stock["positions_value"] + crypto["positions_value"], "return_pct": combined_return})

    st.markdown("### 🏆 Top opportunities")
    if opportunities:
        columns = st.columns(min(len(opportunities), 5))
        for index, (column, opportunity) in enumerate(zip(columns, opportunities), 1):
            payload = parse_json(opportunity.get("payload"))
            opp_action = str(payload.get("action") or "WATCH").upper()
            with column:
                st.markdown(
                    f"""
                    <div class="opp-card">
                      <div class="opp-rank">RANK #{index} · {html.escape(clean_market(opportunity.get('market')).upper())}</div>
                      <div class="opp-symbol">{html.escape(str(opportunity.get('symbol') or '—'))}</div>
                      <span class="pill {action_class(opp_action)}">{html.escape(opp_action)}</span>
                      <div class="stars">{star_rating(opportunity.get('opportunity_score'))}</div>
                      <div class="muted">Score {as_float(opportunity.get('opportunity_score')):.1f}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("Opportunity rankings will appear after the workers complete a V3 scan.")

    st.markdown("### ⚙️ Live workers")
    w1, w2 = st.columns(2)
    with w1:
        render_worker("Stock Worker", "📈", workers_by_market.get("stock", {}))
    with w2:
        render_worker("Crypto Worker", "₿", workers_by_market.get("crypto", {}))

    st.markdown("### 🧾 Recent activity")
    recent = safe_rows("SELECT market,symbol,side,quantity,price,value,realized_pnl,created_at FROM trades ORDER BY id DESC LIMIT 8")
    if recent:
        for trade in recent:
            side = str(trade.get("side", "HOLD")).upper()
            market_label = clean_market(trade.get("market")).title()
            st.markdown(
                f"**{side} {trade.get('symbol','—')}** · {market_label} · {money(trade.get('value'))} at {money(trade.get('price'))}"
            )
    else:
        st.caption("No trades recorded yet.")

with portfolio_tab:
    st.header("Portfolio")
    st.caption("A clean view of what the workers own and how much capital is available.")
    for title, market, data, positions in [
        ("Stock Portfolio", "cash", stock, stock_positions),
        ("Crypto Portfolio", "crypto", crypto, crypto_positions),
    ]:
        st.subheader(title)
        x, y, z, r = st.columns(4)
        x.metric("Equity", money(data["equity"]), pct(data["return_pct"]))
        y.metric("Available Cash", money(data["cash"]))
        z.metric("Invested", money(data["positions_value"]))
        r.metric("Open Positions", len(positions))
        if positions:
            frame = pd.DataFrame(positions)
            keep = [c for c in ["symbol", "quantity", "average_price", "current_price", "highest_price", "opened_at"] if c in frame.columns]
            st.dataframe(frame[keep], use_container_width=True, hide_index=True)
        else:
            st.info(f"The {title.lower()} has no open positions.")

    snapshots = safe_rows("SELECT market,equity,created_at FROM equity_snapshots ORDER BY id DESC LIMIT 1000")
    if snapshots:
        frame = pd.DataFrame(snapshots)
        frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
        frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")
        frame["market"] = frame["market"].map(clean_market)
        st.plotly_chart(px.line(frame.sort_values("created_at"), x="created_at", y="equity", color="market", title="Portfolio equity over time"), use_container_width=True)

with council_tab:
    st.header("Oracle Council")
    st.caption("The clearest view of what the AI recommends right now.")

    signals = safe_rows(
        "SELECT market,symbol,score,action,confidence,details,created_at FROM signals ORDER BY id DESC LIMIT 30"
    )
    if signals:
        buys = [x for x in signals if str(x.get("action") or "").upper() == "BUY"]
        sells = [x for x in signals if str(x.get("action") or "").upper() == "SELL"]
        holds = [x for x in signals if str(x.get("action") or "HOLD").upper() == "HOLD"]
        avg_conf = sum(normalized_confidence(x.get("confidence")) for x in signals) / max(len(signals), 1)

        st.markdown(
            f"""
            <div class="decision-summary">
              <div class="summary-box"><small>Buy opportunities</small><b>🟢 {len(buys)}</b></div>
              <div class="summary-box"><small>Watch / hold</small><b>🟡 {len(holds)}</b></div>
              <div class="summary-box"><small>Average confidence</small><b>{avg_conf:.0f}%</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="plain-note"><b>How to read this:</b> BUY means the setup passed the council. HOLD means watch it, but do not enter yet. SELL means risk increased or the setup weakened.</div>',
            unsafe_allow_html=True,
        )

        filter_choice = st.segmented_control(
            "Show decisions",
            options=["Best first", "Buy only", "Hold only", "Sell only"],
            default="Best first",
        )
        filtered = list(signals)
        if filter_choice == "Buy only":
            filtered = buys
        elif filter_choice == "Hold only":
            filtered = holds
        elif filter_choice == "Sell only":
            filtered = sells
        else:
            priority = {"BUY": 0, "SELL": 1, "HOLD": 2}
            filtered = sorted(
                filtered,
                key=lambda x: (
                    priority.get(str(x.get("action") or "HOLD").upper(), 3),
                    -normalized_confidence(x.get("confidence")),
                    -as_float(x.get("score")),
                ),
            )

        st.subheader("Latest decisions")
        if filtered:
            cards: list[str] = []
            for item in filtered[:18]:
                decision_action = str(item.get("action") or "HOLD").upper()
                decision_confidence = normalized_confidence(item.get("confidence"))
                decision_score = as_float(item.get("score"))
                decision_details = parse_json(item.get("details"))
                decision_reason = str(
                    decision_details.get("reason")
                    or decision_details.get("explanation")
                    or decision_details.get("summary")
                    or "The council reviewed trend, momentum, volume, news, and risk."
                )
                created = pd.to_datetime(item.get("created_at"), errors="coerce", utc=True)
                if pd.isna(created):
                    time_text = "Latest scan"
                else:
                    time_text = created.strftime("%b %d · %I:%M %p UTC")
                market_text = "Stocks" if clean_market(item.get("market")) == "stock" else "Crypto"
                score_label = "Strong" if decision_score >= 0.65 else "Moderate" if decision_score >= 0.5 else "Developing"
                cards.append(
                    f"""
                    <div class="decision-item">
                      <div class="decision-top">
                        <div class="decision-name">{html.escape(str(item.get('symbol') or '—'))}</div>
                        <span class="pill {action_class(decision_action)}">{html.escape(decision_action)}</span>
                      </div>
                      <div class="decision-meta"><span>{market_text}</span><span>•</span><span>{html.escape(time_text)}</span></div>
                      <div class="decision-score">
                        <div class="decision-stat"><small>Confidence</small><b>{decision_confidence:.0f}%</b></div>
                        <div class="decision-stat"><small>Setup strength</small><b>{score_label}</b></div>
                      </div>
                      <div class="decision-reason"><b>Why:</b> {html.escape(short_reason(decision_reason))}</div>
                    </div>
                    """
                )
            render_html('<div class="decision-list">' + ''.join(textwrap.dedent(card).strip() for card in cards) + '</div>')
        else:
            st.info("No decisions match this filter.")
    else:
        st.info("Council decisions will appear after the next worker scan.")

    with st.expander("Meet the 12 council specialists"):
        specialists = [
            ("Chief Market Strategist", "Combines the full market signal."),
            ("Trend & Momentum", "Checks whether price direction is strong and persistent."),
            ("Dip Specialist", "Looks for oversold rebound opportunities."),
            ("Liquidity & Volume", "Checks trading activity and unusual volume."),
            ("Macro Regime", "Adjusts for risk-on and risk-off conditions."),
            ("News Catalyst", "Evaluates headlines and upcoming events."),
            ("Risk & Drawdown", "Protects the portfolio from unstable setups."),
            ("Opportunity Ranker", "Compares each asset against the alternatives."),
            ("Portfolio Rotation", "Moves capital toward stronger opportunities."),
            ("Crypto Structure", "Handles digital-asset volatility."),
            ("Equity Quality", "Evaluates stock quality and durability."),
            ("Devil's Advocate", "Challenges the final decision before approval."),
        ]
        cols = st.columns(2)
        for index, (name, description) in enumerate(specialists):
            with cols[index % 2]:
                st.markdown(
                    f'<div class="vote-row"><b>{html.escape(name)}</b><br><span class="muted">{html.escape(description)}</span></div>',
                    unsafe_allow_html=True,
                )

with radar_tab:
    st.header("Market Radar")
    st.caption("Rankings, catalysts, whale activity, flow, Congress, insiders, macro, and regulatory signals.")
    market_choice = st.radio("Market", ["cash", "crypto"], horizontal=True, format_func=lambda value: "Stocks" if value == "cash" else "Crypto")
    opportunities_all = safe_rows(
        """
        SELECT DISTINCT ON (symbol) symbol,rank,opportunity_score,payload,created_at
        FROM opportunity_rankings
        WHERE market=%s
        ORDER BY symbol,created_at DESC
        """,
        (market_choice,),
    )
    opportunities_all = sorted(opportunities_all, key=lambda x: as_float(x.get("opportunity_score")), reverse=True)
    if opportunities_all:
        radar_frame = pd.DataFrame([
            {
                "Rank": index,
                "Symbol": item.get("symbol"),
                "Score": as_float(item.get("opportunity_score")),
                "Rating": star_rating(item.get("opportunity_score")),
                "Reason": short_reason(item),
                "Updated": item.get("created_at"),
            }
            for index, item in enumerate(opportunities_all, 1)
        ])
        st.dataframe(radar_frame, use_container_width=True, hide_index=True)
    else:
        st.info("No ranked opportunities have been saved for this market yet.")

    intelligence = safe_rows("SELECT category,provider,symbol,title,event_time,created_at FROM intelligence_events ORDER BY id DESC LIMIT 50")
    st.subheader("Latest intelligence")
    if intelligence:
        st.dataframe(pd.DataFrame(intelligence), use_container_width=True, hide_index=True)
    else:
        st.caption("No intelligence events recorded yet.")

with journal_tab:
    st.header("Trade Journal")
    trades = safe_rows("SELECT market,symbol,side,quantity,price,value,realized_pnl,score,reason,created_at FROM trades ORDER BY id DESC LIMIT 250")
    if trades:
        frame = pd.DataFrame(trades)
        frame["market"] = frame["market"].map(clean_market)
        st.dataframe(frame, use_container_width=True, hide_index=True)
        realized = pd.to_numeric(frame.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0)
        m1, m2, m3 = st.columns(3)
        m1.metric("Trades shown", len(frame))
        m2.metric("Realized P&L", money(realized.sum()))
        m3.metric("Winning exits", int((realized > 0).sum()))
    else:
        st.info("The journal will fill automatically as trades are executed.")

with backtest_tab:
    st.header("Improved Backtesting")
    symbol_input = st.text_input("Symbol", "SPY").upper().strip()
    capital = st.number_input("Starting capital", 100.0, 100000.0, 2000.0, 100.0)
    if st.button("Run backtest", type="primary"):
        history = get_history(symbol_input, "2y", "1d")
        result = run_backtest(symbol_input, history, capital)
        if "error" in result:
            st.error(result["error"])
        else:
            metrics = {key: value for key, value in result.items() if key not in {"equity_curve", "dates", "trade_log"}}
            metric_columns = st.columns(min(4, max(1, len(metrics))))
            for index, (key, value) in enumerate(metrics.items()):
                metric_columns[index % len(metric_columns)].metric(key.replace("_", " ").title(), value)
            chart = pd.DataFrame({"date": pd.to_datetime(result["dates"]), "equity": result["equity_curve"]})
            st.plotly_chart(px.line(chart, x="date", y="equity", title=f"{symbol_input} backtest equity"), use_container_width=True)
            st.dataframe(pd.DataFrame(result["trade_log"]), use_container_width=True, hide_index=True)

with system_tab:
    st.header("System Health")
    s1, s2, s3 = st.columns(3)
    s1.metric("Workers online", f"{workers_online}/2")
    s2.metric("Migrations this boot", len(applied_migrations))
    s3.metric("Database", "Connected")

    st.subheader("Provider diagnostics")
    diagnostics = provider_diagnostics()
    st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)
    st.subheader("API cache")
    st.json(cache_stats())
    st.subheader("Database migrations")
    migration_rows = safe_rows("SELECT version,applied_at FROM schema_migrations ORDER BY version")
    st.dataframe(pd.DataFrame(migration_rows), use_container_width=True, hide_index=True)
    st.subheader("Railway start commands")
    st.code(
        "Web: python start_web.py\n"
        "Stock: python stock_worker.py\n"
        "Crypto: python crypto_worker.py"
    )

st.caption("Simulation only. No brokerage execution. Council decisions, rankings, and forecasts are probabilistic—not guaranteed returns.")
