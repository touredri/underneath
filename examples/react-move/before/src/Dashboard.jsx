import { useState } from 'react';

function StatCard({ title, value, onOpen }) {
  return (
    <div className="stat-card" onClick={onOpen}>
      <h3>{title}</h3>
      <p className="stat-value">{value}</p>
    </div>
  );
}

function TripList({ trips }) {
  return (
    <ul className="trip-list">
      {trips.map((trip) => (
        <li key={trip.id}>
          {trip.from} → {trip.to}
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard({ stats, trips }) {
  const [open, setOpen] = useState(null);
  return (
    <main>
      <header className="dash-header">
        <h1 className="dash-title">Fleet overview</h1>
        <p className="dash-subtitle">{stats.trucks} trucks, {stats.trips} trips this week</p>
        <button type="button" className="dash-refresh" onClick={() => setOpen(null)}>
          Close details
        </button>
      </header>
      <StatCard title="Trucks" value={stats.trucks} onOpen={() => setOpen('trucks')} />
      <StatCard title="Trips" value={stats.trips} onOpen={() => setOpen('trips')} />
      <TripList trips={trips} />
      {open && <p>Showing {open}</p>}
    </main>
  );
}
