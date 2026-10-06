"""Currency conversion via REST Countries (currencies) + a free FX API.
Falls back to a static table when offline so the app never hard-fails."""
import httpx

FX_URL = "https://open.er-api.com/v6/latest/{base}"
FALLBACK = {"USD": 1.0, "INR": 83.0, "EUR": 0.92, "GBP": 0.79}
_cache: dict[str, tuple[float, str]] = {}


def get_rate(base: str, target: str) -> tuple[float, str]:
    """Return (rate, source). source is 'api' | 'cache' | 'fallback'."""
    base, target = base.upper(), target.upper()
    if base == target:
        return 1.0, "none"
    key = f"{base}:{target}"
    try:
        r = httpx.get(FX_URL.format(base=base), timeout=5)
        r.raise_for_status()
        rate = float(r.json()["rates"][target])
        _cache[key] = (rate, "api")
        return rate, "api"
    except Exception:
        if key in _cache:
            return _cache[key][0], "cache"
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
