# Hope-is-near Oracle Council upgrade

Upload every file in this ZIP to the root of the existing GitHub repository and overwrite matching files.

Railway services from the same repository:

- Web: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
- Stock worker: `python stock_worker.py`
- Crypto worker: `python crypto_worker.py`

Share the same `DATABASE_URL` and API variables across all three services. The ZIP includes Python 3.11.9 and Nixpacks settings to avoid the Python 3.12.4 `mise` build error.

The stock and crypto workers run continuously. Stocks only receive meaningful fresh prices when their markets provide data; crypto can update around the clock. This is paper trading.
