import math
import os
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from . import analytics, parsers, store, transform
from .currency import get_rate, country_currencies

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
app = FastAPI(title="Orders Analytics API", version="1.0.0")
app.add_middleware(CORSMiddleware,
                   allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
_cache: dict = {}


def ok(data, **meta):
    return {"success": True, "data": data, "meta": meta}


async def _read(upload: UploadFile | None, default: str):
    if upload is not None:
        return await upload.read()
    p = DATA_DIR / default
    if not p.exists():
        raise HTTPException(404, f"No upload provided and {default} not found")
    return p.read_bytes()


def _guard(fn, *a):
    try:
        return fn(*a)
    except parsers.ParseError as e:
        raise HTTPException(422, str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest/json")
async def ingest_json(file: UploadFile | None = File(None)):
    df = transform.flatten_orders(_guard(parsers.parse_json, await _read(file, "Orders.json")))
    store.save("orders", df); _cache.clear()
    return ok({"rows": len(df), "orders": int(df.order_id.nunique())})


@app.post("/ingest/xml")
async def ingest_xml(file: UploadFile | None = File(None)):
    df = transform.clean_shipments(_guard(parsers.parse_xml, await _read(file, "Shipment.xml")))
    store.save("shipments", df); _cache.clear()
    return ok({"rows": len(df)})


@app.post("/ingest/csv")
async def ingest_csv(file: UploadFile | None = File(None)):
    df = transform.clean_products(_guard(parsers.parse_csv, await _read(file, "Products.csv")))
    store.save("products", df); _cache.clear()
    return ok({"rows": len(df)})


@app.post("/ingest/all")
async def ingest_all():
    """Convenience: load the three bundled sample files."""
    return ok({"json": (await ingest_json(None))["data"],
               "xml": (await ingest_xml(None))["data"],
               "csv": (await ingest_csv(None))["data"]})


def _joined(currency: str):
    orders, products, ships = store.load("orders"), store.load("products"), store.load("shipments")
    if orders.empty:  # cold serverless instance: seed from bundled samples
        _seed_sync()
        orders, products, ships = store.load("orders"), store.load("products"), store.load("shipments")
    try:
        rate, src = get_rate("USD", currency)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return transform.join_all(orders, products, ships, rate), rate, src


@app.get("/analytics/summary")
def analytics_summary(start: str | None = None, end: str | None = None,
                      category: str | None = None, status: str | None = None,
                      currency: str = "USD"):
    key = ("summary", start, end, category, status, currency)
    if key in _cache:
        return _cache[key]
    df, rate, src = _joined(currency)
    d = analytics.apply_filters(df, start, end, category, status)
    result = ok(analytics.summary(d), currency=currency.upper(), rate=rate, rate_source=src,
                options={"categories": sorted(df.category.unique().tolist()),
                         "statuses": sorted(df.status.unique().tolist())})
    _cache[key] = result
    return result


@app.get("/analytics/orders")
def analytics_orders(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                     start: str | None = None, end: str | None = None,
                     category: str | None = None, status: str | None = None,
                     currency: str = "USD"):
    df, _, _ = _joined(currency)
    rows = analytics.order_rows(analytics.apply_filters(df, start, end, category, status))
    total = len(rows)
    chunk = rows.iloc[(page - 1) * page_size: page * page_size]
    return ok(chunk.astype(object).where(chunk.notna(), None).to_dict("records"),
              page=page, page_size=page_size, total=total,
              total_pages=max(1, math.ceil(total / page_size)))


@app.get("/analytics/orders/{order_id}")
def order_detail(order_id: str, currency: str = "USD"):
    df, _, _ = _joined(currency)
    d = df[df.order_id == order_id]
    if d.empty:
        raise HTTPException(404, f"Order {order_id} not found")
    d = d.astype(object).where(d.notna(), None)
    d["order_date"] = d["order_date"].astype(str)
    return ok(d[["product_id", "product_name", "category", "qty", "price",
                 "line_total_converted"]].to_dict("records"),
              order_id=order_id, customer=d.iloc[0]["customer_name"],
              status=d.iloc[0]["status"], delivery_days=d.iloc[0]["delivery_days"])


@app.get("/reference/countries")
def countries():
    try:
        return ok(country_currencies())
    except Exception as e:
        raise HTTPException(502, f"REST Countries API unavailable: {e}")


def _seed_sync():
    store.save("orders", transform.flatten_orders(parsers.parse_json((DATA_DIR / "Orders.json").read_bytes())))
    store.save("shipments", transform.clean_shipments(parsers.parse_xml((DATA_DIR / "Shipment.xml").read_bytes())))
    store.save("products", transform.clean_products(parsers.parse_csv((DATA_DIR / "Products.csv").read_bytes())))


@app.on_event("startup")
def seed():
    if store.load("orders").empty:
        try:
            _seed_sync()
        except Exception as e:  # never block startup
            print("seed failed:", e)
