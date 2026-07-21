# GARIBALDI MARKET ORACLE™ V7 Overhaul

## What changed

- Replaced the old home dashboard with a full financial intelligence workspace.
- Added deterministic market-regime, signal-breadth, provider-coverage and portfolio/system risk calculations.
- Added seven navigation areas: Mission Control, Opportunity Center, Market Intelligence, Portfolio Lab, Research Desk, Risk & Alerts, and System Health.
- Connected the existing OpenAI integration to an in-app research desk and Oracle Council review.
- Preserved all current workers, market scanning, opportunity ranking, portfolio logic, database tables, migrations and Railway configuration.
- Added defensive database queries so a missing optional data set displays an empty state instead of crashing the dashboard.
- Added responsive dashboard styling for desktop and mobile.
- Added `platform_intelligence.py` and automated tests.
- Kept `app_v6_backup.py` as a rollback copy.

## Validation

- Python compilation: passed.
- Automated tests: 12 passed.
- No API keys or Railway variables are included in the ZIP.

## Deployment

Upload the contents to the existing repository. Do not delete PostgreSQL or your Railway variables. Redeploy the existing web, stock-worker and crypto-worker services.
