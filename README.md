# Orders Analytics Dashboard

A full-stack analytics app that ingests orders (JSON), shipments (XML) and products (CSV), joins and cleans them, and serves aggregated metrics to a React dashboard.

**Stack:** FastAPI · pandas · PostgreSQL (SQLite for local dev) · React 18 · Vite · Recharts

## Features

**Backend**
- Ingest endpoints for JSON, XML and CSV (file upload, or the bundled samples)
- Tolerant parsers that repair malformed input (quoted CSV/JSON lines, BOM) and return clear `422` errors
- Flattens nested orders into line items, then LEFT-joins orders + shipments + products
- Derived fields: order value, delivery delay flag, category-level aggregation, currency conversion
- Pagination, filtering (date, category, status, currency), in-memory response caching
- Consistent response envelope: `{ success, data, meta }`

**Frontend**
- KPI cards: total orders, revenue, delayed orders, average order value
- Charts: revenue trend, category revenue, delivery performance
- Filters: date range, category, delivery status, currency
- Revenue / Orders view toggle; click a bar or pie slice to drill down; expandable order rows
- Loading, error (with retry) and empty states; responsive layout

## Project structure

```
backend/
  app/
    main.py        # routes, CORS, caching, startup seeding
    parsers.py     # CSV / JSON / XML parsing + repair
    transform.py   # flatten, clean, join (pure functions)
    analytics.py   # filters and aggregations
    currency.py    # FX rates (API + cache + fallback), REST Countries
    store.py       # persistence: PostgreSQL if DATABASE_URL is set, else SQLite
  data/            # sample Orders.json, Shipment.xml, Products.csv
  tests/
frontend/
  src/
    api.js         # fetch client
    store.jsx      # Context + useReducer state
    components/    # KpiCard, Filters, Charts, OrdersTable
render.yaml        # one-click deploy config (Render)
```

## Getting started

Requires Python 3.10+ and Node 18+.

```bash
# Backend  -> http://localhost:8000  (docs at /docs)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend -> http://localhost:5173
cd frontend
cp .env.example .env
npm install
npm run dev
```

Sample data is loaded automatically on first start (or call `POST /ingest/all`).

### Tests
```bash
cd backend && python -m pytest tests
```

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ingest/json` | Load orders (multipart `file`, optional) |
| POST | `/ingest/xml` | Load shipments |
| POST | `/ingest/csv` | Load products |
| POST | `/ingest/all` | Load all bundled samples |
| GET | `/analytics/summary` | KPIs, revenue trend, category revenue, delivery performance |
| GET | `/analytics/orders` | Paginated orders (`page`, `page_size`) |
| GET | `/analytics/orders/{id}` | Line items for one order |
| GET | `/reference/countries` | Normalised REST Countries to currency data |
| GET | `/health` | Health check |

Shared query params: `start`, `end` (YYYY-MM-DD), `category`, `status`, `currency` (USD, INR, EUR, GBP).

Example:
```bash
curl "http://localhost:8000/analytics/summary?category=Electronics&currency=INR"
```

## Design decisions

- **PostgreSQL in production, SQLite locally:** set `DATABASE_URL` (e.g. a Render/Neon connection string) and the app stores data in Postgres; leave it unset and it uses a local SQLite file, so there is nothing to install for development. Serverless hosts such as Vercel have per-instance throwaway disks, so uploads would be lost on restart and invisible to other instances with SQLite; a hosted database fixes both. Details:
  - tables are replaced inside a single transaction, so concurrent requests never see a half-written table
  - the bundled sample files are loaded only into tables that do not exist yet. Uploaded data (even an empty upload) is never overwritten by samples
  - no idle connections are kept (`NullPool`), which suits short-lived serverless instances
  - `GET /health` reports which backend is active (`"storage": "postgresql"` or `"sqlite"`)
- **pandas:** keeps joins and aggregations concise.
- **LEFT joins:** orders with no matching product or shipment are kept (shown as `Uncategorized` / `No Shipment`) rather than silently dropped.
- **Delay flag:** an order is delayed if its shipment status is `Delayed` or delivery takes more than 5 days.
- **Data-quality rules:** applied while ingesting, and every one is counted and returned in the ingest response under `warnings`:
  - the same `order_id` more than once: the last record wins, the rest are dropped (no double counting)
  - orders without an `order_id`, or entries that are not objects: skipped
  - line items with a negative quantity or price: dropped (the order itself is kept)
  - missing or non-numeric quantity/price: treated as 0
  - dates that are not ISO `YYYY-MM-DD` (e.g. `01/04/2024`, which is ambiguous): not guessed. The order is kept, shown as `Unknown` in the revenue trend (so the trend always adds up to the KPIs), and excluded when a date filter is active
- **Errors:** unusable input (wrong JSON shape, broken XML/CSV, an invalid `start`/`end` date) always returns a 422 with a `detail` message, never a 500.
- **FX rates:** fetched from the exchange-rate API and cached for an hour (one response caches every currency). If the API fails, the last known rate is used, then a built-in fallback table, and the API is not retried for a minute.
- **Currency:** live rates from open.er-api.com, cached, with an offline fallback; `meta.rate_source` reports which was used.
- **State management:** Context + reducer is enough for this app's size; filters changes refetch automatically.

## Deployment

`render.yaml` defines the API and the static frontend.
1. Deploy the API, copy its URL into the frontend's `VITE_API_URL`.
2. Set the API's `CORS_ORIGINS` to the frontend URL.

Free-tier disks are ephemeral; the sample data re-seeds on each start.

## License
MIT
