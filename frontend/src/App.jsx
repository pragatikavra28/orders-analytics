import { useEffect, useState } from "react";
import { useStore } from "./store";
import { seedData } from "./api";
import KpiCard from "./components/KpiCard";
import Filters from "./components/Filters";
import OrdersTable from "./components/OrdersTable";
import ProductsPage from "./components/ProductsPage";
import ShipmentsPage from "./components/ShipmentsPage";
import { RevenueTrend, CategoryRevenue, DeliveryPerformance } from "./components/Charts";

const fmt = (n, cur) => new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n);

const TABS = [
  ["dashboard", "Dashboard", "Hi, welcome back"],
  ["orders", "Orders", "Orders"],
  ["products", "Products", "Products"],
  ["shipments", "Shipments", "Shipments"],
];

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const { state, dispatch, reload } = useStore();
  const { summary, loading, error, filters } = state;
  const d = summary?.data;
  const usesOrders = tab === "dashboard" || tab === "orders";
  const title = TABS.find((t) => t[0] === tab)[2];

  useEffect(() => { dispatch({ type: "pageSize", payload: tab === "orders" ? 10 : 5 }); }, [tab, dispatch]);

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">◆ Orders</div>
        <nav>
          {TABS.map(([id, label]) => (
            <a key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</a>
          ))}
        </nav>
      </aside>
      <main>
        <h1>{title}</h1>
        {tab === "products" && <ProductsPage />}
        {tab === "shipments" && <ShipmentsPage />}
        {usesOrders && <Filters />}
        {usesOrders && error && (
          <div className="banner err">
            {error}
            <span>
              <button onClick={reload}>Retry</button>{" "}
              <button onClick={async () => { await seedData(); reload(); }}>Load sample data</button>
            </span>
          </div>
        )}
        {usesOrders && loading && <div className="loading">Loading…</div>}
        {usesOrders && tab === "orders" && d && <OrdersTable />}
        {usesOrders && tab === "dashboard" && d && (
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
        {usesOrders && !loading && !error && d && d.kpis.total_orders === 0 && <div className="empty">No orders match these filters.</div>}
      </main>
    </div>
  );
}
