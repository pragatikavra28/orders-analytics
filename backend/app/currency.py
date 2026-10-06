"""Currency conversion via REST Countries (currencies) + a free FX API.
Falls back to a static table when offline so the app never hard-fails."""
import time

import httpx

FX_URL = "https://open.er-api.com/v6/latest/{base}"
FALLBACK = {"USD": 1.0, "INR": 83.0, "EUR": 0.92, "GBP": 0.79}
TTL_SECONDS = 3600        # a fetched rate is reused for an hour
RETRY_AFTER_SECONDS = 60  # after a failed call, don't hit the API again for a minute
_cache: dict[str, tuple[float, float]] = {}  # "USD:INR" -> (rate, fetched_at)
_api_down_until = 0.0


def get_rate(base: str, target: str) -> tuple[float, str]:
    """Return (rate, source). source is 'none' | 'api' | 'cache' | 'fallback'.

    One API response carries every rate for the base currency, so all of them
    are cached together: later requests (any target) cost no network call.
    """
    global _api_down_until
    base, target = base.upper(), target.upper()
    if base == target:
        return 1.0, "none"
    key, now = f"{base}:{target}", time.time()
    hit = _cache.get(key)
    if hit and now - hit[1] < TTL_SECONDS:
        return hit[0], "cache"
    if now >= _api_down_until:
        try:
            r = httpx.get(FX_URL.format(base=base), timeout=5)
            r.raise_for_status()
            rates = r.json()["rates"]
            for code, value in rates.items():
                _cache[f"{base}:{code.upper()}"] = (float(value), now)
            return float(rates[target]), "api"
        except Exception:
            _api_down_until = now + RETRY_AFTER_SECONDS
    if hit:  # stale beats a hard-coded table
        return hit[0], "cache"
    if base in FALLBACK and target in FALLBACK:
        return round(FALLBACK[target] / FALLBACK[base], 6), "fallback"
    raise ValueError(f"No rate available for {base}->{target}")


def country_currencies(limit: int = 250) -> list[dict]:
    """Normalise the nested REST Countries payload into country->currency rows."""
    r = httpx.get("https://restcountries.com/v3.1/all?fields=name,currencies,population,region",
                  timeout=10)
    r.raise_for_status()
    rows = []
    for c in r.json()[:limit]:
        for code, meta in (c.get("currencies") or {}).items():
            rows.append({"country": c["name"]["common"], "region": c.get("region"),
                         "population": c.get("population"), "currency": code,
                         "currency_name": meta.get("name")})
    return rows
