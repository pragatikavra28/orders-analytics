import { ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { useStore } from "../store";

const COLORS = ["#1d62d6", "#1890ff", "#ffc107", "#ff4842", "#54d62c", "#7a4fff"];

function Card({ title, sub, children, right }) {
  return (
    <div className="card chart-card">
      <div className="card-head"><div><h3>{title}</h3>{sub && <small>{sub}</small>}</div>{right}</div>
      <div className="chart-body">{children}</div>
    </div>
  );
}

export function RevenueTrend({ data }) {
  const { state, dispatch } = useStore();
  const key = state.view; // revenue | orders
  const toggle = (
    <div className="toggle">
      {["revenue", "orders"].map((v) => (
        <button key={v} className={key === v ? "on" : ""}
          onClick={() => dispatch({ type: "view", payload: v })}>
          {v === "revenue" ? "Revenue" : "Orders"}</button>
      ))}
    </div>
  );
  return (
    <Card title={`${key === "revenue" ? "Revenue" : "Orders"} trend`} sub="Daily, filtered" right={toggle}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" /><YAxis allowDecimals={false} /><Tooltip />
          <Line type="monotone" dataKey={key} stroke="#1d62d6" strokeWidth={3} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

// Clicking a bar drills down: sets the category filter, which refilters everything.
export function CategoryRevenue({ data }) {
  const { state, dispatch } = useStore();
  const key = state.view;
  return (
    <Card title="Category-wise revenue" sub="Click a bar to drill down">
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="category" /><YAxis /><Tooltip />
          <Bar dataKey={key} radius={[6, 6, 0, 0]} cursor="pointer"
            onClick={(d) => dispatch({ type: "filters", payload: { category: d.category } })}>
            {data.map((d, i) => (
              <Cell key={d.category} fill={state.filters.category === d.category ? "#ff4842" : COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export function DeliveryPerformance({ data }) {
  const { dispatch } = useStore();
  return (
    <Card title="Delivery performance" sub="Click a slice to filter">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="count" nameKey="status" outerRadius="75%" label
            cursor="pointer" onClick={(d) => dispatch({ type: "filters", payload: { status: d.status } })}>
            {data.map((d, i) => <Cell key={d.status} fill={COLORS[(i + 3) % COLORS.length]} />)}
          </Pie>
          <Tooltip /><Legend />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  );
}
