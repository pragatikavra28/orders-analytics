import { useEffect, useState } from "react";
import { useStore } from "../store";
import { fetchProducts } from "../api";

export default function ProductsPage() {
  const { state, dispatch } = useStore();
  const currency = state.filters.currency;
  const [s, setS] = useState({ loading: true, rows: [], error: null });
  const [n, setN] = useState(0); // bump to retry

  useEffect(() => {
    let live = true;
    setS({ loading: true, rows: [], error: null });
    fetchProducts(currency)
      .then((r) => live && setS({ loading: false, rows: r.data, error: null }))
      .catch((e) => live && setS({ loading: false, rows: [], error: e.message }));
    return () => { live = false; };
  }, [currency, n]);

  const picker = (
    <div className="card filters">
      <label>Currency
        <select value={currency} onChange={(e) => dispatch({ type: "filters", payload: { currency: e.target.value } })}>
          {["USD", "INR", "EUR", "GBP"].map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
    </div>
  );

  if (s.loading) return <>{picker}<div className="loading">Loading…</div></>;
  if (s.error) return (
    <>{picker}<div className="banner err">{s.error}<button onClick={() => setN(n + 1)}>Retry</button></div></>
  );
  if (!s.rows.length) return <>{picker}<div className="empty">No products found.</div></>;

  return (
    <>{picker}
    <div className="card">
      <div className="card-head"><h3>Products <small>({s.rows.length})</small></h3></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Product</th><th>Category</th>
            <th className="num">Orders</th><th className="num">Units sold</th>
            <th className="num">Revenue ({currency})</th></tr></thead>
          <tbody>
            {s.rows.map((p) => (
              <tr key={p.product_id}>
                <td>{p.product_id}</td><td>{p.product_name}</td><td>{p.category}</td>
                <td className="num">{p.orders}</td><td className="num">{p.units_sold}</td>
                <td className="num">{p.revenue.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}
