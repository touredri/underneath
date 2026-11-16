export function StatCard({ title, value, onOpen }) {
  return (
    <div className="stat-card" onClick={onOpen}>
      <h3>{title}</h3>
      <p className="stat-value">{value}</p>
    </div>
  );
}
