const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null)
  ).toString();
  const res = await fetch(`${BASE}${path}${qs ? "?" + qs : ""}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

export const fetchSummary = (f) => get("/analytics/summary", f);
export const fetchOrders = (f, page, page_size = 5) =>
  get("/analytics/orders", { ...f, page, page_size });
export const fetchOrder = (id, currency) => get(`/analytics/orders/${id}`, { currency });
export const seedData = () =>
  fetch(`${BASE}/ingest/all`, { method: "POST" }).then((r) => r.json());
