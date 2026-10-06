const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null)
  ).toString();
  const res = await fetch(`${BASE}${path}${qs ? "?" + qs : ""}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    // FastAPI sends a string for our errors but a list of {msg} for validation errors
    const d = body.detail;
    const msg = Array.isArray(d) ? d.map((e) => e.msg).join("; ") : d;
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return body;
}

export const fetchSummary = (f) => get("/analytics/summary", f);
export const fetchProducts = (currency) => get("/analytics/products", { currency });
export const fetchShipments = () => get("/analytics/shipments");
export const fetchOrders = (f, page, page_size = 5) =>
  get("/analytics/orders", { ...f, page, page_size });
export const fetchOrder = (id, currency) => get(`/analytics/orders/${id}`, { currency });
export const seedData = () =>
  fetch(`${BASE}/ingest/all`, { method: "POST" }).then((r) => r.json());
