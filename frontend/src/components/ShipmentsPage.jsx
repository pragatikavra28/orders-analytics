import { useEffect, useState } from "react";
import { fetchShipments } from "../api";
import KpiCard from "./KpiCard";

export default function ShipmentsPage() {
  const [s, setS] = useState({ loading: true, rows: [], meta: null, error: null });
  const [n, setN] = useState(0); // bump to retry

  useEffect(() => {
    let live = true;
    setS({ loading: true, rows: [], meta: null, error: null });
    fetchShipments()
      .then((r) => live && setS({ loading: false, rows: r.data, meta: r.meta, error: null }))
      .catch((e) => live && setS({ loading: false, rows: [], meta: null, error: e.message }));
    return () => { live = false; };
  }, [n]);

  if (s.loading) return <div className="loading">Loading…</div>;
  if (s.error) return (
    <div className="banner err">{s.error}<button onClick={() => setN(n + 1)}>Retry</button></div>
  );
  if (!s.rows.length) return <div className="empty">No shipments found.</div>;

  const { total, delayed } = s.meta;
  return (
    <>
      <section className="kpis" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
        <KpiCard tone="blue" label="Total Shipments" value={total} />
        <KpiCard tone="red" label="Delayed" value={delayed} />
        <KpiCard tone="cyan" label="On Time" value={total - delayed} />
      </section>
      <div className="card">
        <div className="card-head"><h3>Shipments <small>({total})</small></h3></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Shipment</th><th>Order</th><th className="num">Delivery days</th><th>Status</th></tr></thead>
            <tbody>
              {s.rows.map((r) => (
                <tr key={r.shipment_id}>
                  <td>{r.shipment_id}</td><td>#{r.order_id}</td>
                  <td className="num">{r.delivery_days ?? "—"}</td>
                  <td><span className={`pill ${r.delayed ? "bad" : "good"}`}>{r.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
