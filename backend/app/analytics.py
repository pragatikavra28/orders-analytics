import pandas as pd


def apply_filters(df, start=None, end=None, category=None, status=None):
    if df.empty:
        return df
    d = df.copy()
    d["order_date"] = pd.to_datetime(d["order_date"], errors="coerce")
    if start:
        d = d[d["order_date"] >= pd.to_datetime(start)]
    if end:
        d = d[d["order_date"] <= pd.to_datetime(end)]
    if category:
        d = d[d["category"] == category]
    if status:
        d = d[d["status"] == status]
    return d


def summary(d: pd.DataFrame, value_col="line_total_converted") -> dict:
    if d.empty:
        return {"kpis": {"total_orders": 0, "total_revenue": 0, "delayed_orders": 0,
                         "avg_order_value": 0},
                "revenue_trend": [], "category_revenue": [], "delivery_performance": []}
    per_order = d.groupby("order_id").agg(
        value=(value_col, "sum"), delayed=("delayed", "max"),
        date=("order_date", "first"), status=("status", "first")).reset_index()
    trend = d.groupby(d["order_date"].dt.strftime("%Y-%m-%d")).agg(
        revenue=(value_col, "sum"), orders=("order_id", "nunique")).reset_index()
    trend.columns = ["date", "revenue", "orders"]
    cat = d.groupby("category").agg(
        revenue=(value_col, "sum"), orders=("order_id", "nunique"),
        units=("qty", "sum")).reset_index().sort_values("revenue", ascending=False)
    deliv = per_order.groupby("status").size().reset_index(name="count")
    return {
        "kpis": {"total_orders": int(per_order.shape[0]),
                 "total_revenue": round(float(per_order["value"].sum()), 2),
                 "delayed_orders": int(per_order["delayed"].sum()),
                 "avg_order_value": round(float(per_order["value"].mean()), 2)},
        "revenue_trend": trend.round(2).to_dict("records"),
        "category_revenue": cat.round(2).to_dict("records"),
        "delivery_performance": deliv.to_dict("records"),
    }


def order_rows(d: pd.DataFrame, value_col="line_total_converted") -> pd.DataFrame:
    """One row per order with items rolled up (used for pagination + drill-down)."""
    if d.empty:
        return d
    g = d.groupby("order_id").agg(
        order_date=("order_date", lambda s: s.iloc[0].strftime("%Y-%m-%d") if pd.notna(s.iloc[0]) else None),
        customer=("customer_name", "first"), total=(value_col, "sum"),
        items=("qty", "sum"), status=("status", "first"),
        delivery_days=("delivery_days", "first"), delayed=("delayed", "max"),
        categories=("category", lambda s: ", ".join(sorted(set(s))))).reset_index()
    g["total"] = g["total"].round(2)
    g["delivery_days"] = g["delivery_days"].where(g["delivery_days"].notna(), None)
    return g
