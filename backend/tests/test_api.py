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
