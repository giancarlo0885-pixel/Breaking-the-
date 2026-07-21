from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
import time
from typing import Any, Callable

from api_manager import KEY_NAMES


@dataclass
class ProviderDiagnostic:
    provider: str
    configured: bool
    status: str
    latency_ms: float | None
    message: str
    checked_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _credential_present(name: str) -> bool:
    aliases = {
        "NEWS_API_KEY": ("NEWS_API_KEY", "NEWSAPI_API_KEY"),
    }
    candidates = aliases.get(name, (name,))
    return any(bool(os.getenv(candidate, "").strip()) for candidate in candidates)


def diagnose_provider(
    name: str,
    probe: Callable[[], Any] | None = None,
) -> ProviderDiagnostic:
    configured = _credential_present(name)

    if not configured:
        return ProviderDiagnostic(
            provider=name,
            configured=False,
            status="not_configured",
            latency_ms=None,
            message="API key is not configured.",
            checked_at=_now(),
        )

    if probe is None:
        return ProviderDiagnostic(
            provider=name,
            configured=True,
            status="configured",
            latency_ms=None,
            message="Credential detected; no network probe requested.",
            checked_at=_now(),
        )

    started = time.perf_counter()

    try:
        probe()
        latency = (time.perf_counter() - started) * 1000
        return ProviderDiagnostic(
            provider=name,
            configured=True,
            status="healthy",
            latency_ms=round(latency, 1),
            message="Probe completed successfully.",
            checked_at=_now(),
        )
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        return ProviderDiagnostic(
            provider=name,
            configured=True,
            status="degraded",
            latency_ms=round(latency, 1),
            message=str(exc)[:240],
            checked_at=_now(),
        )


def _provider_names() -> list[str]:
    required_names = [
        "ALPHA_VANTAGE_API_KEY",
        "EODHD_API_KEY",
        "FINNHUB_API_KEY",
        "NEWS_API_KEY",
        "OPENAI_API_KEY",
    ]

    optional_names = [
        "POLYGON_API_KEY",
        "FRED_API_KEY",
        "NASDAQ_DATA_LINK_API_KEY",
        "SEC_API_KEY",
        "QUIVER_API_KEY",
        "UNUSUAL_WHALES_API_KEY",
        "COINGLASS_API_KEY",
    ]

    combined = list(KEY_NAMES) + required_names + optional_names
    return list(dict.fromkeys(combined))


def provider_diagnostics() -> list[dict[str, Any]]:
    records = [
        asdict(diagnose_provider(name))
        for name in _provider_names()
    ]

    records.insert(
        0,
        asdict(
            ProviderDiagnostic(
                provider="YAHOO_FINANCE",
                configured=True,
                status="available",
                latency_ms=None,
                message="Primary public market-data fallback.",
                checked_at=_now(),
            )
        ),
    )

    return records


if __name__ == "__main__":
    import json

    print(json.dumps(provider_diagnostics(), indent=2))
