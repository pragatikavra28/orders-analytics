import { useStore } from "./store";
import { seedData } from "./api";
import KpiCard from "./components/KpiCard";
import Filters from "./components/Filters";
import OrdersTable from "./components/OrdersTable";
import { RevenueTrend, CategoryRevenue, DeliveryPerformance } from "./components/Charts";

const fmt = (n, cur) => new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n);

export default function App() {
  const { state, reload } = useStore();
  const { summary, loading, error, filters } = state;
  const d = summary?.data;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">◆ Orders</div>
        <nav><a className="active">Dashboard</a><a>Orders</a><a>Products</a><a>Shipments</a></nav>
      </aside>
      <main>
        <h1>Hi, welcome back</h1>
        <Filters />
        {error && (
          <div className="banner err">
            {error}
            <span>
              <button onClick={reload}>Retry</button>{" "}
              <button onClick={async () => { await seedData(); reload(); }}>Load sample data</button>
            </span>
          </div>
        )}
        {loading && <div className="loading">Loading…</div>}
        {d && (
          <>
            <section className="kpis">
              <KpiCard tone="blue" label="Total Orders" value={d.kpis.total_orders} />
              <KpiCard tone="cyan" label="Total Revenue" value={fmt(d.kpis.total_revenue, filters.currency)} />
              <KpiCard tone="red" label="Delayed Orders" value={d.kpis.delayed_orders} />
              <KpiCard tone="yellow" label="Avg Order Value" value={fmt(d.kpis.avg_order_value, filters.currency)} />
            </section>
            <section className="grid2">
              <RevenueTrend data={d.revenue_trend} />
              <DeliveryPerformance data={d.delivery_performance} />
            </section>
            <section className="grid2 even">
              <CategoryRevenue data={d.category_revenue} />
              <OrdersTable />
            </section>
            {summary.meta.rate_source === "fallback" && (
              <small className="note">Currency rate is an offline fallback.</small>
            )}
          </>
        )}
        {!loading && !error && d && d.kpis.total_orders === 0 && <div className="empty">No orders match these filters.</div>}
      </main>
    </div>
  );
}
