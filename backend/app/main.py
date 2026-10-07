import math
import os
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd

from . import analytics, parsers, store, transform
from .errors import BadRequest
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


@app.exception_handler(BadRequest)
async def bad_request_handler(_: Request, exc: BadRequest):
    """Unusable input (bad file shape, bad date, ...) is always a clean 422."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "storage": store.backend()}


@app.post("/ingest/json")
async def ingest_json(file: UploadFile | None = File(None)):
    df = transform.flatten_orders(parsers.parse_json(await _read(file, "Orders.json")))
    store.save("orders", df); _cache.clear()
    return ok({"rows": len(df), "orders": int(df.order_id.nunique()),
               "warnings": df.attrs.get("quality", {})})


@app.post("/ingest/xml")
async def ingest_xml(file: UploadFile | None = File(None)):
    df = transform.clean_shipments(parsers.parse_xml(await _read(file, "Shipment.xml")))
    store.save("shipments", df); _cache.clear()
    return ok({"rows": len(df), "warnings": df.attrs.get("quality", {})})


@app.post("/ingest/csv")
async def ingest_csv(file: UploadFile | None = File(None)):
    df = transform.clean_products(parsers.parse_csv(await _read(file, "Products.csv")))
    store.save("products", df); _cache.clear()
    return ok({"rows": len(df), "warnings": df.attrs.get("quality", {})})


@app.post("/ingest/all")
async def ingest_all():
    """Convenience: load the three bundled sample files."""
    return ok({"json": (await ingest_json(None))["data"],
               "xml": (await ingest_xml(None))["data"],
               "csv": (await ingest_csv(None))["data"]})


def _joined(currency: str):
    orders, products, ships = store.load("orders"), store.load("products"), store.load("shipments")
    if _seed_missing():  # first run: fill any table that was never loaded
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


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> None)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


@app.get("/analytics/products")
def analytics_products(currency: str = "USD"):
    """Product catalogue with units sold and revenue per product."""
    df, _, _ = _joined(currency)  # also seeds a cold instance
    products = store.load("products")
    agg = (df.dropna(subset=["product_id"])
             .groupby("product_id")
             .agg(units_sold=("qty", "sum"), orders=("order_id", "nunique"),
                  revenue=("line_total_converted", "sum"))
             .reset_index())
    out = products.merge(agg, on="product_id", how="left")
    out["units_sold"] = out["units_sold"].fillna(0).astype(int)
    out["orders"] = out["orders"].fillna(0).astype(int)
    out["revenue"] = out["revenue"].fillna(0.0).round(2)
    out = out.sort_values("revenue", ascending=False)
    return ok(_records(out), currency=currency.upper(), total=len(out))


@app.get("/analytics/shipments")
def analytics_shipments():
    """All shipments, with the delayed flag used by the dashboard."""
    _joined("USD")  # seeds a cold instance
    ships = store.load("shipments")
    if not ships.empty:
        ships["delayed"] = ships["delayed"].astype(bool)
        ships = ships.sort_values("shipment_id")
    return ok(_records(ships), total=len(ships),
              delayed=int(ships["delayed"].sum()) if not ships.empty else 0)


@app.get("/reference/countries")
def countries():
    try:
        return ok(country_currencies())
    except Exception as e:
        raise HTTPException(502, f"REST Countries API unavailable: {e}")


def _seed_missing() -> bool:
    """Load the bundled sample file for every table that does not exist yet.

    Keyed on table *existence*, not emptiness, so an upload is never replaced by
    the samples. Returns True if anything was seeded."""
    seeded = False
    if not store.exists("orders"):
        store.save("orders", transform.flatten_orders(parsers.parse_json((DATA_DIR / "Orders.json").read_bytes())))
        seeded = True
    if not store.exists("shipments"):
        store.save("shipments", transform.clean_shipments(parsers.parse_xml((DATA_DIR / "Shipment.xml").read_bytes())))
        seeded = True
    if not store.exists("products"):
        store.save("products", transform.clean_products(parsers.parse_csv((DATA_DIR / "Products.csv").read_bytes())))
        seeded = True
    return seeded


@app.on_event("startup")
def seed():
    try:
        _seed_missing()
    except Exception as e:  # never block startup
        print("seed failed:", e)
