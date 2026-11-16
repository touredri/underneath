import { useState } from 'react';
import { DashboardHeader } from './dash/DashboardHeader';
import { EmptyState } from './dash/EmptyState';
import { StatCard } from './dash/StatCard';
import { TripList } from './dash/TripList';

export default function Dashboard({ stats, trips, onReload }) {
  const [open, setOpen] = useState(null);
  if (!stats) {
    return <EmptyState message="No data yet." onRetry={onReload} />;
  }
  return (
    <main>
      <DashboardHeader stats={stats} setOpen={setOpen} />
      <StatCard title="Trucks" value={stats.trucks} onOpen={() => setOpen('trucks')} />
      <StatCard title="Trips" value={stats.trips} onOpen={() => setOpen('trips')} />
      <TripList trips={trips} />
      {open && <p>Showing {open}</p>}
    </main>
  );
}
