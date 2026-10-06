export default function KpiCard({ label, value, tone }) {
  return (
    <div className={`kpi ${tone}`}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
