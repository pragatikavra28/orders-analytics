import { useStore } from "../store";

export default function Filters() {
  const { state, dispatch } = useStore();
  const { filters, options } = state;
  const set = (k) => (e) => dispatch({ type: "filters", payload: { [k]: e.target.value } });
  return (
    <div className="card filters">
      <label>From<input type="date" value={filters.start} onChange={set("start")} /></label>
      <label>To<input type="date" value={filters.end} onChange={set("end")} /></label>
      <label>Category
        <select value={filters.category} onChange={set("category")}>
          <option value="">All</option>
          {options.categories.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <label>Delivery status
        <select value={filters.status} onChange={set("status")}>
          <option value="">All</option>
          {options.statuses.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <label>Currency
        <select value={filters.currency} onChange={set("currency")}>
          {["USD", "INR", "EUR", "GBP"].map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <button className="ghost" onClick={() => dispatch({ type: "filters",
        payload: { start: "", end: "", category: "", status: "" } })}>Reset</button>
    </div>
  );
}
