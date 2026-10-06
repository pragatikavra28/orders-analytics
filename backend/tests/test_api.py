import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["CORS_ORIGINS"] = "*"
from fastapi.testclient import TestClient
from app import main, parsers
from app.currency import get_rate

main.get_rate = lambda b, t: (1.0 if t == "USD" else 83.0, "test")
client = TestClient(main.app)


def test_parsers_repair_messy_files():
    assert parsers.parse_csv((main.DATA_DIR / "Products.csv").read_bytes())[0]["ProductID"] == "P101"
    j = parsers.parse_json((main.DATA_DIR / "Orders.json").read_bytes())
    assert len(j["orders"]) == 2
    assert parsers.parse_xml((main.DATA_DIR / "Shipment.xml").read_bytes())[1]["status"] == "Delayed"


def test_ingest_and_summary():
    with client:
        assert client.post("/ingest/all").json()["success"]
        d = client.get("/analytics/summary").json()["data"]
    k = d["kpis"]
    assert k["total_orders"] == 2
    assert k["total_revenue"] == 2800 + 600 - 0 or k["total_revenue"] == 2200 + 600
    assert k["delayed_orders"] == 1
    cats = {c["category"]: c["revenue"] for c in d["category_revenue"]}
    assert cats == {"Electronics": 2200, "Furniture": 600}


def test_filters_pagination_currency_detail():
    with client:
        client.post("/ingest/all")
        assert client.get("/analytics/summary?category=Furniture").json()["data"]["kpis"]["total_orders"] == 1
        assert client.get("/analytics/summary?status=Delivered").json()["data"]["kpis"]["total_orders"] == 1
        o = client.get("/analytics/orders?page=1&page_size=1").json()
        assert o["meta"]["total"] == 2 and o["meta"]["total_pages"] == 2
        assert client.get("/analytics/summary?currency=INR").json()["data"]["kpis"]["total_revenue"] == 2800 * 83
        assert len(client.get("/analytics/orders/1001").json()["data"]) == 2
        assert client.get("/analytics/orders/9999").status_code == 404


def test_bad_upload_returns_422():
    with client:
        r = client.post("/ingest/xml", files={"file": ("x.xml", b"<a><b></a>")})
    assert r.status_code == 422


def test_products_and_shipments_endpoints():
    with client:
        client.post("/ingest/all")
        p = client.get("/analytics/products").json()
        by_id = {r["product_id"]: r for r in p["data"]}
        assert p["meta"]["total"] == 3
        assert by_id["P101"]["units_sold"] == 2 and by_id["P101"]["revenue"] == 1000
        assert by_id["P103"]["revenue"] == 600
        inr = client.get("/analytics/products?currency=INR").json()["data"]
        assert {r["product_id"]: r for r in inr}["P103"]["revenue"] == 600 * 83
        s = client.get("/analytics/shipments").json()
        assert s["meta"]["total"] == 2 and s["meta"]["delayed"] == 1
        assert {r["shipment_id"]: r["delayed"] for r in s["data"]} == {"S001": False, "S002": True}


# ---------------------------------------------------------------------------
# Robustness: bad input must never be a 500, and data-quality rules must hold
# ---------------------------------------------------------------------------
import json
import time

from app import currency


def _load(orders):
    """Ingest a custom orders payload plus the bundled products/shipments."""
    r = client.post("/ingest/json", files={"file": ("o.json", json.dumps(orders).encode())})
    client.post("/ingest/csv"); client.post("/ingest/xml")
    return r


def _order(oid, items, date="2024-01-01", name="A"):
    return {"order_id": oid, "customer": {"id": "C", "name": name},
            "items": items, "order_date": date}


def test_wrong_shape_json_is_422_not_500():
    with client:
        for raw in (b'"hello"', b"42", b"null", b'{"orders": "x"}', b'{"nope": []}'):
            r = client.post("/ingest/json", files={"file": ("x.json", raw)})
            assert r.status_code == 422, (raw, r.status_code)
            assert "detail" in r.json()
        # garbage entries inside a valid list are skipped and reported, not fatal
        r = client.post("/ingest/json", files={"file": ("x.json", b'[1, "x", {"items": []}]')})
        assert r.status_code == 200
        w = r.json()["data"]["warnings"]
        assert w["skipped_malformed_orders"] == 2 and w["skipped_orders_without_id"] == 1


def test_bad_date_filter_is_422_not_500():
    with client:
        client.post("/ingest/all")
        for url in ("/analytics/summary?start=garbage", "/analytics/summary?end=2024-13-45",
                    "/analytics/orders?start=nope"):
            r = client.get(url)
            assert r.status_code == 422 and "YYYY-MM-DD" in r.json()["detail"], url
        assert client.get("/analytics/summary?start=2024-01-01&end=2024-12-31").status_code == 200


def test_duplicate_orders_are_not_double_counted():
    with client:
        item = [{"product_id": "P101", "qty": 2, "price": 500}]
        r = _load({"orders": [_order("1", item), _order("1", item), _order("2", item)]})
        assert r.json()["data"]["warnings"]["duplicate_orders_dropped"] == 1
        k = client.get("/analytics/summary").json()["data"]["kpis"]
        assert k["total_orders"] == 2 and k["total_revenue"] == 2000  # not 3000


def test_negative_values_are_dropped_not_summed():
    with client:
        r = _load({"orders": [
            _order("1", [{"product_id": "P101", "qty": 1, "price": 100}]),
            _order("2", [{"product_id": "P102", "qty": -3, "price": 1200}]),
            _order("3", [{"product_id": "P103", "qty": 2, "price": -50}]),
        ]})
        assert r.json()["data"]["warnings"]["items_dropped_negative_values"] == 2
        k = client.get("/analytics/summary").json()["data"]["kpis"]
        assert k["total_revenue"] == 100 and k["total_orders"] == 3  # orders kept, bad lines not


def test_missing_qty_or_price_is_reported():
    with client:
        r = _load({"orders": [_order("1", [{"product_id": "P101", "qty": None, "price": "abc"},
                                           {"product_id": "P102", "qty": "2", "price": "10"}])]})
        assert r.json()["data"]["warnings"]["items_with_missing_or_invalid_qty_or_price"] == 1
        assert client.get("/analytics/summary").json()["data"]["kpis"]["total_revenue"] == 20  # "2"*"10" parsed


def test_undated_orders_keep_trend_and_kpis_consistent():
    with client:
        item = [{"product_id": "P101", "qty": 1, "price": 100}]
        r = _load({"orders": [_order("1", item, "2024-01-01"), _order("2", item, "01/04/2024"),
                              _order("3", item, "not-a-date"), _order("4", item, None)]})
        assert r.json()["data"]["warnings"]["orders_with_missing_or_unparseable_date"] == 3
        d = client.get("/analytics/summary").json()["data"]
        assert d["kpis"]["total_revenue"] == 400
        assert sum(t["revenue"] for t in d["revenue_trend"]) == 400   # trend == KPIs
        assert [t["date"] for t in d["revenue_trend"]] == ["2024-01-01", "Unknown"]
        # an active date filter excludes undated orders
        f = client.get("/analytics/summary?start=2024-01-01").json()["data"]["kpis"]
        assert f["total_orders"] == 1


class _FakeResp:
    def __init__(self, rates): self._r = rates
    def raise_for_status(self): pass
    def json(self): return {"rates": self._r}


def test_fx_rate_is_cached_and_api_failures_back_off(monkeypatch):
    calls = []

    def ok(url, timeout):
        calls.append(url)
        return _FakeResp({"INR": 90.0, "EUR": 0.5})

    currency._cache.clear(); currency._api_down_until = 0.0
    monkeypatch.setattr(currency.httpx, "get", ok)
    assert currency.get_rate("USD", "INR") == (90.0, "api")
    assert currency.get_rate("USD", "INR") == (90.0, "cache")
    assert currency.get_rate("USD", "EUR") == (0.5, "cache")  # same response cached every target
    assert len(calls) == 1

    # API down: falls back, and does not retry on every request
    currency._cache.clear(); currency._api_down_until = 0.0; calls.clear()

    def boom(url, timeout):
        calls.append(url); raise OSError("down")

    monkeypatch.setattr(currency.httpx, "get", boom)
    assert currency.get_rate("USD", "INR") == (83.0, "fallback")
    assert currency.get_rate("USD", "INR") == (83.0, "fallback")
    assert len(calls) == 1
    # a stale cached rate beats the hard-coded table
    currency._cache["USD:INR"] = (91.0, time.time() - currency.TTL_SECONDS - 1)
    currency._api_down_until = 0.0
    assert currency.get_rate("USD", "INR") == (91.0, "cache")
    currency._cache.clear(); currency._api_down_until = 0.0
