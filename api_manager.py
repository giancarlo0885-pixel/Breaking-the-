from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

KEY_NAMES = [
    "ALPHA_VANTAGE_API_KEY",
    "FINNHUB_API_KEY",
    "NEWS_API_KEY",
    "POLYGON_API_KEY",
    "FRED_API_KEY",
    "NASDAQ_DATA_LINK_API_KEY",
    "SEC_API_KEY",
    "QUIVER_API_KEY",
    "UNUSUAL_WHALES_API_KEY",
    "COINGLASS_API_KEY",
    "WHALE_ALERT_API_KEY",
]

@dataclass(frozen=True)
class APISettings:
    values: dict[str, str | None]

    def has(self, name: str) -> bool:
        return bool(self.values.get(name))

def get_api_settings() -> APISettings:
    values = {}
    for name in KEY_NAMES:
        raw = os.getenv(name, "").strip()
        values[name] = raw or None
    return APISettings(values)

def api_status() -> dict[str, bool]:
    settings = get_api_settings()
    return {name.replace("_API_KEY", "").replace("_", " ").title(): settings.has(name) for name in KEY_NAMES}
