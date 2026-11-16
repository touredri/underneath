export function DashboardHeader({ stats, setOpen }) {
  return (
    <header className="dash-header">
      <h1 className="dash-title">Fleet overview</h1>
      <p className="dash-subtitle">{stats.trucks} trucks, {stats.trips} trips this week</p>
      <button type="button" className="dash-refresh" onClick={() => setOpen(null)}>
        Close details
      </button>
    </header>
  );
}
