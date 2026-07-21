from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
import pandas as pd
import yfinance as yf
from cache import cached_call
from config import API_CACHE_TTL_SECONDS

@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    change_pct: float
    volume: float
    timestamp: str

def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    keep = [c for c in ("Open","High","Low","Close","Volume") if c in frame.columns]
    return frame[keep].dropna(subset=["Close"])

def _download_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    try:
        data = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False, threads=False)
        return _normalize(data)
    except Exception:
        return pd.DataFrame()

def get_history(symbol: str, period="1y", interval="1d") -> pd.DataFrame:
    return cached_call("market_history", API_CACHE_TTL_SECONDS, _download_history, symbol, period, interval)

def get_snapshot(symbol: str) -> MarketSnapshot | None:
    h = get_history(symbol, "5d", "1d")
    if h.empty:
        return None
    c = h["Close"].astype(float)
    price = float(c.iloc[-1])
    prev = float(c.iloc[-2]) if len(c)>1 else price
    change = ((price/prev)-1)*100 if prev else 0
    vol = float(h["Volume"].iloc[-1]) if "Volume" in h else 0
    return MarketSnapshot(symbol,price,change,vol,datetime.now(timezone.utc).isoformat())

def get_many_snapshots(symbols: Iterable[str]) -> dict[str, MarketSnapshot]:
    out = {}
    for s in symbols:
        snap = get_snapshot(s)
        if snap:
            out[s] = snap
    return out
