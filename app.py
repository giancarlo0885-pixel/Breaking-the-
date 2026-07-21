from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_oracle import answer_market_question, market_briefing, openai_available, oracle_council
from backtesting import run_backtest
from cache import stats as cache_stats
from config import APP_NAME, STARTING_BALANCE
from dashboard_helpers import as_float, normalized_confidence, parse_json, short_reason, worker_is_online
from database import initialize_database, row, rows
from market_data import get_history
from migrations import run_migrations
from platform_intelligence import build_snapshot, deterministic_brief
from provider_diagnostics import provider_diagnostics

st.set_page_config(page_title=f"{APP_NAME} — Intelligence Platform", page_icon="🔮", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root{--bg:#071018;--panel:#0d1823;--panel2:#111f2d;--line:#24384a;--text:#eef5fb;--muted:#94a8ba;--accent:#53e0b3;--purple:#9b87ff;--warn:#ffcc66;--bad:#ff6f7d}
.stApp{background:radial-gradient(circle at 10% 0%,rgba(83,224,179,.12),transparent 30%),radial-gradient(circle at 95% 0%,rgba(155,135,255,.14),transparent 28%),var(--bg)}
.block-container{max-width:1500px;padding-top:1rem;padding-bottom:3rem}.hero{border:1px solid var(--line);background:linear-gradient(135deg,rgba(17,31,45,.98),rgba(9,19,29,.98));border-radius:26px;padding:25px;margin-bottom:14px;box-shadow:0 18px 50px rgba(0,0,0,.24)}
.eyebrow{font-size:.72rem;font-weight:900;letter-spacing:.16em;color:var(--accent);text-transform:uppercase}.hero h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1;margin:.35rem 0}.hero p{color:var(--muted);font-size:1.02rem;max-width:950px}.badge{display:inline-block;padding:.35rem .7rem;border:1px solid var(--line);border-radius:999px;background:#0b1620;margin:.25rem .3rem .1rem 0;color:#cbd8e3;font-size:.82rem}
.kpi{border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,var(--panel2),var(--panel));padding:17px;min-height:128px}.kpi small{color:var(--muted);display:block}.kpi b{font-size:2rem;display:block;margin:.25rem 0}.good{color:var(--accent)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.panel{border:1px solid var(--line);border-radius:20px;background:var(--panel);padding:18px;margin-bottom:12px}.panel h3{margin-top:0}.muted{color:var(--muted)}.opportunity{border:1px solid var(--line);border-radius:16px;background:#0a151f;padding:15px;margin-bottom:9px}.opportunity .symbol{font-size:1.35rem;font-weight:900}.score{font-size:1.5rem;font-weight:900;color:var(--accent)}
.alert-card{border-left:4px solid var(--warn);background:#101b26;border-radius:12px;padding:12px 14px;margin-bottom:8px}.brief{font-size:1.03rem;line-height:1.65;color:#d7e3ec}.status{display:inline-flex;align-items:center;gap:7px}.dot{width:9px;height:9px;border-radius:50%;display:inline-block}.dot.on{background:var(--accent);box-shadow:0 0 12px rgba(83,224,179,.7)}.dot.off{background:var(--bad)}
div[data-testid="stMetric"]{border:1px solid var(--line);border-radius:16px;padding:12px;background:var(--panel)}
@media(max-width:700px){.block-container{padding-left:.7rem;padding-right:.7rem}.hero{padding:18px}.hero h1{font-size:2rem}.kpi b{font-size:1.6rem}}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def bootstrap() -> list[str]:
    initialize_database()
    return run_migrations()


def safe_rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    try:
        return rows(query, params)
    except Exception:
        return []


def safe_row(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    try:
        return row(query, params) or {}
    except Exception:
        return {}


def money(x: Any) -> str:
    return f"${as_float(x):,.2f}"


def get_portfolio(market: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, float]]:
    p = safe_row("SELECT * FROM portfolios WHERE market=%s", (market,))
    pos = safe_rows("SELECT * FROM positions WHERE market=%s ORDER BY symbol", (market,))
    cash = as_float(p.get("cash"), STARTING_BALANCE)
    invested = sum(as_float(x.get("quantity"))*as_float(x.get("current_price")) for x in pos)
    start = as_float(p.get("starting_balance"), STARTING_BALANCE)
    equity = cash + invested
    return p, pos, {"market":market,"cash":cash,"positions_value":invested,"equity":equity,"return_pct":((equity/start)-1)*100 if start else 0}


def latest_opportunities(limit: int = 20) -> list[dict[str, Any]]:
    recs = safe_rows("""SELECT DISTINCT ON (market,symbol) market,symbol,rank,opportunity_score,payload,created_at FROM opportunity_rankings ORDER BY market,symbol,created_at DESC""")
    return sorted(recs,key=lambda x:as_float(x.get("opportunity_score")),reverse=True)[:limit]


def snapshot_context() -> dict[str, Any]:
    stock_p, stock_pos, stock_m = get_portfolio("cash")
    crypto_p, crypto_pos, crypto_m = get_portfolio("crypto")
    signals = safe_rows("SELECT * FROM signals ORDER BY id DESC LIMIT 100")
    opportunities = latest_opportunities(30)
    alerts = safe_rows("SELECT * FROM alerts WHERE acknowledged=0 ORDER BY id DESC LIMIT 30")
    events = safe_rows("SELECT * FROM intelligence_events ORDER BY id DESC LIMIT 40")
    workers = safe_rows("SELECT * FROM market_worker_status ORDER BY market")
    diagnostics = provider_diagnostics()
    snap, risk_reasons = build_snapshot(signals=signals,opportunities=opportunities,positions=stock_pos+crypto_pos,portfolio_metrics=[stock_m,crypto_m],alerts=alerts,diagnostics=diagnostics,workers=workers,worker_online_fn=worker_is_online)
    return {"stock_portfolio":stock_p,"crypto_portfolio":crypto_p,"stock_positions":stock_pos,"crypto_positions":crypto_pos,"portfolios":[stock_m,crypto_m],"signals":signals,"opportunities":opportunities,"alerts":alerts,"events":events,"workers":workers,"diagnostics":diagnostics,"snapshot":snap,"risk_reasons":risk_reasons}


migration_results = bootstrap()
ctx = snapshot_context()
snap = ctx["snapshot"]

with st.sidebar:
    st.markdown("## 🔮 Oracle Navigation")
    page = st.radio("Workspace", ["Mission Control","Opportunity Center","Market Intelligence","Portfolio Lab","Research Desk","Risk & Alerts","System Health"], label_visibility="collapsed")
    st.divider()
    st.caption("Platform mode")
    st.write("**Financial intelligence + simulated execution**")
    st.caption("Workers")
    for market in ("cash","crypto"):
        r = next((x for x in ctx["workers"] if x.get("market")==market),{})
        online = worker_is_online(r.get("status"))
        st.markdown(f'<span class="status"><span class="dot {"on" if online else "off"}"></span>{market.title()} worker: {html.escape(str(r.get("status","waiting")))}</span>',unsafe_allow_html=True)
    if st.button("Refresh intelligence", use_container_width=True):
        st.cache_data.clear(); st.rerun()

st.markdown(f"""<div class="hero"><div class="eyebrow">Global Financial Intelligence Platform</div><h1>{html.escape(APP_NAME)}</h1><p>One command center for market regime, opportunity ranking, portfolio intelligence, institutional signals, economic events, AI research, simulated execution, and system health.</p><span class="badge">Regime: {snap.regime}</span><span class="badge">Risk: {snap.risk_level}</span><span class="badge">Coverage: {snap.provider_coverage:.0f}%</span><span class="badge">Updated {datetime.now(timezone.utc).strftime('%H:%M UTC')}</span></div>""",unsafe_allow_html=True)

if page == "Mission Control":
    c1,c2,c3,c4,c5 = st.columns(5)
    cards=[("Market Regime",snap.regime,f"{snap.regime_score:.0f}/100","good" if snap.regime_score>=56 else "warn"),("Risk Radar",snap.risk_level,f"{snap.risk_score:.0f}/100","bad" if snap.risk_score>=55 else "warn"),("Top Opportunity",snap.top_opportunity or "Waiting",f"{snap.top_opportunity_score:.0f}/100","good"),("Signal Breadth",f"{snap.breadth:+.0f}",f"{snap.bullish_signals} buy / {snap.bearish_signals} sell","good" if snap.breadth>=0 else "bad"),("Workers Online",f"{snap.workers_online}/{snap.workers_expected}",f"{snap.active_alerts} active alerts","good" if snap.workers_online>=snap.workers_expected else "bad")]
    for col,(label,value,sub,klass) in zip((c1,c2,c3,c4,c5),cards):
        col.markdown(f'<div class="kpi"><small>{label}</small><b class="{klass}">{value}</b><span class="muted">{sub}</span></div>',unsafe_allow_html=True)
    left,right=st.columns([1.35,1])
    with left:
        st.markdown("### Executive Intelligence Brief")
        brief = deterministic_brief(snap,ctx["risk_reasons"])
        st.markdown(f'<div class="panel brief">{html.escape(brief)}</div>',unsafe_allow_html=True)
        if openai_available() and st.button("Generate AI market briefing"):
            with st.spinner("Analyzing current platform data…"):
                st.markdown(market_briefing({"snapshot":snap.to_dict(),"opportunities":ctx["opportunities"][:10],"alerts":ctx["alerts"][:10],"events":ctx["events"][:15],"portfolios":ctx["portfolios"]}))
        st.markdown("### Portfolio Command")
        pcols=st.columns(2)
        for col,data,title in zip(pcols,ctx["portfolios"],["Stock Portfolio","Crypto Portfolio"]):
            klass="good" if data["return_pct"]>=0 else "bad"
            col.markdown(f'<div class="panel"><h3>{title}</h3><div class="score">{money(data["equity"])}</div><div class="{klass}">{data["return_pct"]:+.2f}% return</div><div class="muted">Cash {money(data["cash"])} · Invested {money(data["positions_value"])}</div></div>',unsafe_allow_html=True)
    with right:
        st.markdown("### Priority Opportunities")
        if not ctx["opportunities"]: st.info("No rankings yet. The workers create rankings after completing scans.")
        for i,x in enumerate(ctx["opportunities"][:6],1):
            st.markdown(f'<div class="opportunity"><div class="muted">#{i} · {html.escape(str(x.get("market",""))).upper()}</div><div class="symbol">{html.escape(str(x.get("symbol","—")))}</div><div class="score">{as_float(x.get("opportunity_score")):.1f}/100</div><div class="muted">{html.escape(short_reason(x,130))}</div></div>',unsafe_allow_html=True)
        st.markdown("### Risk Watch")
        for reason in ctx["risk_reasons"]:
            st.markdown(f'<div class="alert-card">{html.escape(reason)}</div>',unsafe_allow_html=True)

elif page == "Opportunity Center":
    st.markdown("## Opportunity Center")
    st.caption("Ranked decision support—not a profit guarantee. Filter the full stock and crypto opportunity universe.")
    market_filter=st.selectbox("Market",["All","cash","crypto"])
    opps=[x for x in ctx["opportunities"] if market_filter=="All" or x.get("market")==market_filter]
    if opps:
        df=pd.DataFrame([{"Rank":i+1,"Market":x.get("market"),"Symbol":x.get("symbol"),"Opportunity Score":round(as_float(x.get("opportunity_score")),1),"Reason":short_reason(x,180),"Updated":x.get("created_at")} for i,x in enumerate(opps)])
        st.dataframe(df,use_container_width=True,hide_index=True)
        sym=st.selectbox("Open opportunity",[x.get("symbol") for x in opps])
        selected=next(x for x in opps if x.get("symbol")==sym)
        payload=parse_json(selected.get("payload"))
        a,b=st.columns([1,1])
        a.metric("Opportunity score",f"{as_float(selected.get('opportunity_score')):.1f}/100")
        a.write(short_reason(selected,500))
        b.json(payload or {"message":"No extended ranking payload saved."})
    else: st.info("No ranked opportunities are stored yet.")

elif page == "Market Intelligence":
    st.markdown("## Market Intelligence")
    tabs=st.tabs(["Signal Map","Event Stream","Economic Lens","Sector Pulse"])
    with tabs[0]:
        sig=ctx["signals"]
        if sig:
            df=pd.DataFrame([{"Market":x.get("market"),"Symbol":x.get("symbol"),"Action":x.get("action"),"Score":as_float(x.get("score")),"Confidence":normalized_confidence(x.get("confidence")),"Price":as_float(x.get("price")),"Time":x.get("created_at")} for x in sig])
            st.dataframe(df,use_container_width=True,hide_index=True)
        else: st.info("No signals yet.")
    with tabs[1]:
        for x in ctx["events"]:
            st.markdown(f'<div class="panel"><b>{html.escape(str(x.get("title","Event")))}</b><div class="muted">{html.escape(str(x.get("category","")))} · {html.escape(str(x.get("provider","")))} · {html.escape(str(x.get("symbol") or "Global"))}</div><p>{html.escape(short_reason(x.get("details"),350))}</p></div>',unsafe_allow_html=True)
        if not ctx["events"]: st.info("No intelligence events stored yet.")
    with tabs[2]:
        cats={}
        for x in ctx["events"]: cats[str(x.get("category","other"))]=cats.get(str(x.get("category","other")),0)+1
        if cats:
            fig=px.bar(pd.DataFrame({"Category":list(cats),"Events":list(cats.values())}),x="Category",y="Events",title="Intelligence coverage by category")
            st.plotly_chart(fig,use_container_width=True)
        else: st.info("Economic and macro modules will populate this view as providers return data.")
    with tabs[3]:
        st.write("Current breadth combines the latest worker decisions across stocks and crypto.")
        st.metric("Breadth",f"{snap.breadth:+.1f}")
        st.progress(max(0,min(100,int((snap.breadth+100)/2))))

elif page == "Portfolio Lab":
    st.markdown("## Portfolio Lab")
    market=st.segmented_control("Portfolio",options=["cash","crypto"],default="cash")
    p,positions,m= get_portfolio(market)
    a,b,c,d=st.columns(4); a.metric("Equity",money(m["equity"])); b.metric("Cash",money(m["cash"])); c.metric("Invested",money(m["positions_value"])); d.metric("Return",f"{m['return_pct']:+.2f}%")
    if positions:
        df=pd.DataFrame([{"Symbol":x.get("symbol"),"Quantity":as_float(x.get("quantity")),"Average Price":as_float(x.get("average_price") or x.get("entry_price")),"Current Price":as_float(x.get("current_price")),"Market Value":as_float(x.get("quantity"))*as_float(x.get("current_price")),"Unrealized P&L":as_float(x.get("quantity"))*(as_float(x.get("current_price"))-as_float(x.get("average_price") or x.get("entry_price")))} for x in positions])
        st.dataframe(df,use_container_width=True,hide_index=True)
        fig=px.pie(df,values="Market Value",names="Symbol",title="Position concentration")
        st.plotly_chart(fig,use_container_width=True)
    else: st.info("This portfolio currently has no open positions.")
    st.markdown("### Backtest Workbench")
    symbol=st.text_input("Symbol",value="SPY" if market=="cash" else "BTC-USD").upper().strip()
    if st.button("Run backtest"):
        try:
            result=run_backtest(symbol=symbol,market=market)
            st.json(result)
        except TypeError:
            try: st.json(run_backtest(symbol))
            except Exception as exc: st.error(f"Backtest could not run: {exc}")
        except Exception as exc: st.error(f"Backtest could not run: {exc}")

elif page == "Research Desk":
    st.markdown("## AI Research Desk")
    st.caption("Ask questions using the data already collected by your platform. The assistant is instructed not to invent missing live information.")
    symbols=sorted({str(x.get("symbol")) for x in ctx["signals"]+ctx["opportunities"] if x.get("symbol")})
    selected=st.selectbox("Research symbol",symbols or ["SPY"])
    question=st.text_area("Question",value=f"Give me the bull case, bear case, biggest risk, and what would confirm the setup for {selected}.")
    c1,c2=st.columns(2)
    if c1.button("Ask Oracle",use_container_width=True):
        if not openai_available(): st.warning("Add OPENAI_API_KEY to Railway to activate AI research.")
        else:
            relevant_signals=[x for x in ctx["signals"] if x.get("symbol")==selected][:10]
            relevant_opps=[x for x in ctx["opportunities"] if x.get("symbol")==selected][:5]
            with st.spinner("Building research answer…"):
                st.markdown(answer_market_question(question,{"platform_snapshot":snap.to_dict(),"symbol":selected,"signals":relevant_signals,"opportunities":relevant_opps,"events":ctx["events"][:20]}))
    if c2.button("Run Oracle Council",use_container_width=True):
        if not openai_available(): st.warning("Add OPENAI_API_KEY to Railway to activate the Oracle Council.")
        else:
            with st.spinner("Council specialists are reviewing the evidence…"):
                st.markdown(oracle_council(selected,{"signals":[x for x in ctx["signals"] if x.get("symbol")==selected][:10],"opportunities":[x for x in ctx["opportunities"] if x.get("symbol")==selected],"events":ctx["events"][:20]}))

elif page == "Risk & Alerts":
    st.markdown("## Risk Center")
    a,b,c=st.columns(3); a.metric("Platform risk",snap.risk_level); b.metric("Risk score",f"{snap.risk_score:.1f}/100"); c.metric("Active alerts",snap.active_alerts)
    for reason in ctx["risk_reasons"]: st.markdown(f'<div class="alert-card">{html.escape(reason)}</div>',unsafe_allow_html=True)
    st.markdown("### Alert Feed")
    if ctx["alerts"]:
        st.dataframe(pd.DataFrame(ctx["alerts"]),use_container_width=True,hide_index=True)
    else: st.success("No unacknowledged alerts are stored.")

elif page == "System Health":
    st.markdown("## System Health")
    tabs=st.tabs(["Providers","Workers","Database & Cache","Deployment Checklist"])
    with tabs[0]:
        d=pd.DataFrame(ctx["diagnostics"])
        st.dataframe(d,use_container_width=True,hide_index=True)
        st.metric("Configured provider coverage",f"{snap.provider_coverage:.0f}%")
    with tabs[1]:
        st.dataframe(pd.DataFrame(ctx["workers"]) if ctx["workers"] else pd.DataFrame([{"status":"No worker heartbeat stored"}]),use_container_width=True,hide_index=True)
    with tabs[2]:
        st.write("Migrations applied this launch:",migration_results or "Database already current")
        try: st.json(cache_stats())
        except Exception as exc: st.caption(f"Cache stats unavailable: {exc}")
    with tabs[3]:
        st.markdown("""1. Keep PostgreSQL plus the web, stock-worker, and crypto-worker services.  
2. Web start command: `python start_web.py`.  
3. Stock worker: `python worker.py` with `WORKER_MARKET=cash`.  
4. Crypto worker: `python worker.py` with `WORKER_MARKET=crypto`.  
5. Link the same `DATABASE_URL` to all three services.  
6. Add provider keys only in Railway Variables—never commit them to GitHub.  
7. Confirm both worker heartbeats turn online here before enabling real users.""")

st.divider()
st.caption("GARIBALDI MARKET ORACLE™ provides research and simulated decision support. It does not guarantee performance or replace licensed financial advice.")
