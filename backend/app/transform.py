"""Cleaning, flattening and joining logic (pure functions, no I/O)."""
import pandas as pd

DELAY_THRESHOLD_DAYS = 5


def flatten_orders(payload) -> pd.DataFrame:
    """Nested orders JSON -> one row per order line item."""
    orders = payload.get("orders", []) if isinstance(payload, dict) else payload
    rows = []
    for o in orders or []:
        cust = o.get("customer") or {}
        items = o.get("items") or [{}]  # keep orders that have no items
        for it in items:
            rows.append({
                "order_id": str(o.get("order_id", "")).strip(),
                "order_date": o.get("order_date"),
                "customer_id": cust.get("id"),
                "customer_name": cust.get("name"),
                "product_id": it.get("product_id"),
                "qty": it.get("qty"),
                "price": it.get("price"),
            })
    df = pd.DataFrame(rows, columns=[
        "order_id", "order_date", "customer_id", "customer_name",
        "product_id", "qty", "price"])
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["line_total"] = df["qty"] * df["price"]
    df["customer_name"] = df["customer_name"].fillna("Unknown")
    return df


def clean_products(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["ProductID", "ProductName", "Category"])
    df = df.rename(columns={"ProductID": "product_id",
                            "ProductName": "product_name",
                            "Category": "category"})
    df["category"] = df["category"].replace("", pd.NA).fillna("Uncategorized")
    return df.drop_duplicates("product_id")


def clean_shipments(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["shipment_id", "order_id",
                                     "delivery_days", "status"])
    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce")
    df["status"] = df["status"].replace("", pd.NA).fillna("Unknown").str.title()
    # Inconsistency handling: status says Delayed but days look fine (or reverse)
    df["delayed"] = (df["status"] == "Delayed") | (
        df["delivery_days"].fillna(0) > DELAY_THRESHOLD_DAYS)
    return df.drop_duplicates("order_id")


def join_all(orders: pd.DataFrame, products: pd.DataFrame,
             shipments: pd.DataFrame, rate: float = 1.0) -> pd.DataFrame:
    """Left-join so orders without a product/shipment record are kept."""
    df = orders.merge(products, on="product_id", how="left") \
               .merge(shipments, on="order_id", how="left")
    df["product_name"] = df["product_name"].fillna("Unknown")
    df["category"] = df["category"].fillna("Uncategorized")
    df["status"] = df["status"].fillna("No Shipment")
    df["delayed"] = df["delayed"].fillna(False).astype(bool)
    df["line_total_converted"] = (df["line_total"] * rate).round(2)
    return df
