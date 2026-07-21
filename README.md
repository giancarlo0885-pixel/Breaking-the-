# GARIBALDI MARKET ORACLE™ — Oracle Council V3


## Railway service commands

Use the existing Railway project and PostgreSQL service. Do not delete your variables.

- Web: `python start_web.py`
- Stock worker: `python stock_worker.py`
- Crypto worker: `python crypto_worker.py`

Link `DATABASE_URL` to all three services. The web process starts even when PostgreSQL is unavailable and displays the database error in the dashboard instead of producing a silent 502.

Railway-ready market intelligence and simulated trading platform with one PostgreSQL database and three services: **web**, **stock-worker**, and **crypto-worker**.

## V3 upgrade

- $2,000 stock portfolio and $2,000 crypto portfolio
- Oracle Council V3 with 12 weighted specialists
- Cross-watchlist opportunity ranking
- Portfolio-rotation proposals and persistence tables
- Friction-aware backtesting with fees, slippage, stops, drawdown, Sharpe ratio, trade log, and equity curve
- In-process API/market-data caching
- Provider credential diagnostics
- Mission Control Streamlit dashboard
- Versioned PostgreSQL migrations
- Automated unit tests and Python compilation checks
- Railway service-specific deployment files

## Architecture

All three services deploy from this repository and share the same `DATABASE_URL`:

```text
web            -> streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
stock-worker   -> python stock_worker.py
crypto-worker  -> python crypto_worker.py
```

Do not create separate databases. Link the same Railway PostgreSQL `DATABASE_URL` variable into all three services.

## Required Railway variables

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
STARTING_BALANCE=2000
STOCK_STARTING_BALANCE=2000
CRYPTO_STARTING_BALANCE=2000
WORKER_INTERVAL_SECONDS=300
ENABLE_AUTOTRADE=true
ENABLE_NEWS=true
API_CACHE_TTL_SECONDS=300
ROTATION_ENABLED=true
ROTATION_MIN_SCORE_GAP=8
OPPORTUNITY_LIMIT=12
```

Optional provider keys remain server-side Railway variables. Never commit credentials.

## Database migrations

`initialize_database()` creates the legacy-compatible core schema. `migrations.py` then applies every unapplied SQL file in `migrations/` and records it in `schema_migrations`. Migration `001_oracle_v3.sql` adds opportunity rankings, rotation history, provider health, backtest runs, and portfolio risk fields.

Existing positions and trades are preserved. New empty portfolios initialize at $2,000. Existing funded portfolios are not silently reset.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m compileall -q .
pytest -q
```

A live application boot also requires a PostgreSQL `DATABASE_URL`.

## Railway deployment

Create exactly three services from the same GitHub repository and use:

- `railway.web.json` as the web reference
- `railway.stock-worker.json` as the stock worker reference
- `railway.crypto-worker.json` as the crypto worker reference

The root `railway.json`, `Dockerfile`, and `Procfile` remain included for compatibility.

## Safety

This is paper trading and market research software. It does not connect to a brokerage, execute real orders, or guarantee returns. Premium intelligence modules report missing providers rather than fabricating data.

## Simplified Oracle Home dashboard

The default Streamlit page now prioritizes immediate answers:

- Current Oracle decision, confidence, rating, and plain-language reason
- Stock, crypto, and combined portfolio scorecards
- Top five ranked opportunities
- Stock and crypto worker health
- Recent activity in readable one-line entries

Detailed positions, Council V3 signals, market radar, trade journal, backtesting,
provider diagnostics, cache statistics, and database migrations remain available
in dedicated tabs.

## Version 7 — Financial Intelligence Platform Overhaul

This package upgrades the project from a trading-centered dashboard to a seven-workspace financial intelligence platform:

- Mission Control with regime, breadth, portfolio, risk, worker and opportunity intelligence
- Opportunity Center with unified stock/crypto rankings
- Market Intelligence with signal maps and event streams
- Portfolio Lab with concentration analysis and backtesting access
- AI Research Desk using the existing OpenAI Responses API integration
- Risk Center with operational and portfolio warnings
- System Health with provider coverage, worker heartbeat, migration and deployment checks

The existing stock worker, crypto worker, execution engine, PostgreSQL schema, migrations and Railway service layout remain compatible. `app_v6_backup.py` is included as a rollback copy of the prior dashboard.

## Institutional-style quantitative trade gate

Version 8 adds `quant_trade_standard.py`. Every automatic entry is now evaluated for alpha, execution quality, portfolio risk, relative value, net expected value after costs, and adverse-selection risk. See `ORACLE_QUANT_STANDARD.md` for formulas and Railway controls.
