"""Cleaning, flattening and joining logic (pure functions, no I/O).

Data-quality rules (each one is counted in ``df.attrs["quality"]`` and returned
to the caller as ``warnings`` by the ingest endpoints):

* the same ``order_id`` appearing more than once  -> last record wins, others dropped
* orders without an ``order_id`` / entries that are not objects -> skipped
* line items with a negative qty or price          -> dropped
* missing / non-numeric qty or price               -> treated as 0
* dates that are not ISO (YYYY-MM-DD)              -> kept, date left empty ("Unknown")
"""
import math
from collections import Counter

import pandas as pd

from .errors import BadRequest

DELAY_THRESHOLD_DAYS = 5
_COLS = ["order_id", "order_date", "customer_id", "customer_name",
         "product_id", "qty", "price"]


def _num(v):
    """Best-effort float; None for missing / non-numeric / NaN / bool."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def flatten_orders(payload) -> pd.DataFrame:
    """Nested orders JSON -> one row per order line item."""
    if isinstance(payload, dict):
        orders = payload.get("orders")
        if not isinstance(orders, list):
            raise BadRequest('JSON object must contain an "orders" list')
    elif isinstance(payload, list):
        orders = payload
    else:
        raise BadRequest('JSON must be an object with an "orders" list, or a list of orders')

    q = Counter()
    latest: dict[str, dict] = {}  # order_id -> record (last one wins)
    for o in orders:
        if not isinstance(o, dict):
            q["skipped_malformed_orders"] += 1
            continue
        oid = "" if o.get("order_id") is None else str(o["order_id"]).strip()
        if not oid:
            q["skipped_orders_without_id"] += 1
            continue
        if oid in latest:
            q["duplicate_orders_dropped"] += 1
        latest[oid] = o

    rows = []
    for oid, o in latest.items():
        cust = o.get("customer") if isinstance(o.get("customer"), dict) else {}
        if not cust.get("name"):
            q["orders_missing_customer_name"] += 1
        items = o.get("items") if isinstance(o.get("items"), list) else []
        kept = 0
        for it in items:
            if not isinstance(it, dict):
                q["skipped_malformed_items"] += 1
                continue
            qty, price = _num(it.get("qty")), _num(it.get("price"))
            if qty is None or price is None:
                q["items_with_missing_or_invalid_qty_or_price"] += 1
            if (qty or 0) < 0 or (price or 0) < 0:
                q["items_dropped_negative_values"] += 1
                continue
            rows.append({"order_id": oid, "order_date": o.get("order_date"),
                         "customer_id": cust.get("id"), "customer_name": cust.get("name"),
                         "product_id": it.get("product_id"),
                         "qty": int(qty or 0), "price": price or 0.0})
            kept += 1
        if kept == 0:  # keep the order itself, with a blank line, so it still counts
            if not items:
                q["orders_without_items"] += 1
            rows.append({"order_id": oid, "order_date": o.get("order_date"),
                         "customer_id": cust.get("id"), "customer_name": cust.get("name"),
                         "product_id": None, "qty": 0, "price": 0.0})

    df = pd.DataFrame(rows, columns=_COLS)
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce", format="ISO8601")
    bad_dates = df.loc[df["order_date"].isna(), "order_id"].nunique()
    if bad_dates:
        q["orders_with_missing_or_unparseable_date"] = int(bad_dates)
    df["qty"] = df["qty"].astype(int)
    df["price"] = df["price"].astype(float)
    df["line_total"] = df["qty"] * df["price"]
    df["customer_name"] = df["customer_name"].fillna("Unknown")
    df.attrs["quality"] = dict(q)
    return df


def clean_products(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["ProductID", "ProductName", "Category"])
    df = df.rename(columns={"ProductID": "product_id",
                            "ProductName": "product_name",
                            "Category": "category"})
    df["category"] = df["category"].replace("", pd.NA).fillna("Uncategorized")
    out = df.drop_duplicates("product_id")
    out.attrs["quality"] = {"duplicate_products_dropped": len(df) - len(out)} if len(df) != len(out) else {}
    return out


def clean_shipments(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["shipment_id", "order_id",
                                     "delivery_days", "status"])
    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce")
    df["status"] = df["status"].replace("", pd.NA).fillna("Unknown").str.title()
    # Inconsistency handling: status says Delayed OR days exceed the threshold
    df["delayed"] = (df["status"] == "Delayed") | (
        df["delivery_days"].fillna(0) > DELAY_THRESHOLD_DAYS)
    out = df.drop_duplicates("order_id")
    q = {}
    if len(df) != len(out):
        q["duplicate_shipments_dropped"] = len(df) - len(out)
    if int(out["delivery_days"].isna().sum()):
        q["shipments_missing_delivery_days"] = int(out["delivery_days"].isna().sum())
    out.attrs["quality"] = q
    return out


def join_all(orders: pd.DataFrame, products: pd.DataFrame,
             shipments: pd.DataFrame, rate: float = 1.0) -> pd.DataFrame:
    """Left-join so orders without a product/shipment record are kept."""
    df = orders.merge(products, on="product_id", how="left") \
               .merge(shipments, on="order_id", how="left")
    df["product_name"] = df["product_name"].fillna("Unknown")
    df["category"] = df["category"].fillna("Uncategorized")
    df["status"] = df["status"].fillna("No Shipment")
    df["delayed"] = df["delayed"].astype("boolean").fillna(False).astype(bool)
    df["line_total_converted"] = (df["line_total"] * rate).round(2)
    return df
