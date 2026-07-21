# GARIBALDI MARKET ORACLE V6 — Stability Fix

## Fixed
- Repaired the dashboard crash: `short_reason() takes 1 positional argument but 2 were given`.
- `short_reason()` now safely accepts either a database record or plain text, with an optional maximum length.
- Added regression tests for both supported call forms.
- Verified every Python file compiles.
- Verified the complete automated test suite passes: 10 tests.
- Kept Railway web startup bound to `0.0.0.0:$PORT` through `python start_web.py`.
- Kept PostgreSQL initialization and automatic migrations, including `opportunity_rankings`.

## Railway services
Use the same repository for all three services:

- Web: `python start_web.py`
- Stock worker: `python stock_worker.py`
- Crypto worker: `python crypto_worker.py`

Link the same PostgreSQL `DATABASE_URL` variable to all three services.
Do not manually type a fixed port. Railway supplies `PORT` to the web service.

## Safe replacement
Upload the contents of this ZIP to the root of the GitHub repository. Do not place the files inside an extra folder.
