import { Fragment, useState } from "react";
import { useStore } from "../store";
import { fetchOrder } from "../api";

export default function OrdersTable() {
  const { state, dispatch } = useStore();
  const { orders, page, filters } = state;
  const [open, setOpen] = useState(null);
  const [detail, setDetail] = useState({ loading: false, rows: [], error: null });
  if (!orders) return null;
  const { total_pages, total } = orders.meta;

  async function toggle(id) {
    if (open === id) return setOpen(null);
    setOpen(id); setDetail({ loading: true, rows: [], error: null });
    try {
      const r = await fetchOrder(id, filters.currency);
      setDetail({ loading: false, rows: r.data, error: null });
    } catch (e) { setDetail({ loading: false, rows: [], error: e.message }); }
  }

  return (
    <div className="card">
      <div className="card-head"><h3>Orders <small>({total})</small></h3></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Order</th><th>Date</th><th>Customer</th><th>Categories</th>
            <th>Total ({filters.currency})</th><th>Delivery</th></tr></thead>
          <tbody>
            {orders.data.map((o) => (
              <Fragment key={o.order_id}>
                <tr className="row" onClick={() => toggle(o.order_id)}>
                  <td>#{o.order_id}</td><td>{o.order_date}</td><td>{o.customer}</td>
                  <td>{o.categories}</td><td>{o.total.toLocaleString()}</td>
                  <td><span className={`pill ${o.delayed ? "bad" : "good"}`}>
                    {o.status}{o.delivery_days != null ? ` · ${o.delivery_days}d` : ""}</span></td>
                </tr>
                {open === o.order_id && (
                  <tr className="detail"><td colSpan="6">
                    {detail.loading ? "Loading items…" : detail.error ? <span className="err">{detail.error}</span> :
                      detail.rows.map((r) => (
                        <div key={r.product_id}>{r.product_name} ({r.category}) — {r.qty} × {r.price} = {r.line_total_converted.toLocaleString()}</div>
                      ))}
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button className="ghost" disabled={page <= 1} onClick={() => dispatch({ type: "page", payload: page - 1 })}>Prev</button>
        <span>Page {page} of {total_pages}</span>
        <button className="ghost" disabled={page >= total_pages} onClick={() => dispatch({ type: "page", payload: page + 1 })}>Next</button>
      </div>
    </div>
  );
}
