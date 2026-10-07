"""Storage: PostgreSQL when DATABASE_URL is set, otherwise SQLite.

Why a hosted database: on serverless hosts (Vercel) every instance has its own
ephemeral disk, so SQLite there loses uploads on restart and never shares them
between instances. Postgres is shared and durable. SQLite stays as the zero-setup
default for local development and tests.

Design notes
* NullPool: serverless instances are short-lived, so no idle connections are kept.
* save() replaces a table inside ONE transaction (Postgres DDL is transactional),
  so concurrent readers never see a half-written or missing table.
"""
import os

import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import NullPool

_sqlite_default = ("/tmp/app.db" if os.environ.get("VERCEL")
                   else os.path.join(os.path.dirname(__file__), "..", "data", "app.db"))
DB_PATH = os.environ.get("DB_PATH", _sqlite_default)


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{DB_PATH}"
    for prefix in ("postgres://", "postgresql://"):  # normalise to the psycopg2 driver
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


URL = _url()
IS_POSTGRES = URL.startswith("postgresql")
_kwargs = {"poolclass": NullPool}
if IS_POSTGRES:
    _kwargs["connect_args"] = {"sslmode": os.environ.get("PGSSLMODE", "require"),
                               "connect_timeout": 10}
engine = create_engine(URL, **_kwargs)


def backend() -> str:
    return "postgresql" if IS_POSTGRES else "sqlite"


def exists(name: str) -> bool:
    return inspect(engine).has_table(name)


def save(name: str, df: pd.DataFrame):
    d = df.copy()
    for col in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[col]):
            d[col] = d[col].dt.strftime("%Y-%m-%d")
    with engine.begin() as c:  # single transaction: drop + create + insert
        d.to_sql(name, c, if_exists="replace", index=False)


def load(name: str) -> pd.DataFrame:
    if not exists(name):
        return pd.DataFrame()
    with engine.connect() as c:
        return pd.read_sql_table(name, c)
