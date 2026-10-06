"""SQLite storage (chosen over in-memory so data survives restarts and the
filters in /analytics can be pushed down as SQL). Thread-safe via per-call
connections."""
import sqlite3
from contextlib import contextmanager
import pandas as pd
import os

_default = "/tmp/app.db" if os.environ.get("VERCEL") else os.path.join(os.path.dirname(__file__), "..", "data", "app.db")
DB_PATH = os.environ.get("DB_PATH", _default)


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def save(name: str, df: pd.DataFrame):
    d = df.copy()
    for col in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[col]):
            d[col] = d[col].dt.strftime("%Y-%m-%d")
    with conn() as c:
        d.to_sql(name, c, if_exists="replace", index=False)


def load(name: str) -> pd.DataFrame:
    with conn() as c:
        try:
            return pd.read_sql(f"SELECT * FROM {name}", c)
        except Exception:
            return pd.DataFrame()
