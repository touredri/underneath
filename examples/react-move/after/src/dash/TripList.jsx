export function TripList({ trips }) {
  const active = trips.filter((trip) => trip.status !== 'DONE');
  return (
    <ul className="trip-list">
      {active.map((trip) => (
        <li key={trip.id}>
          {trip.from} → {trip.to}
        </li>
      ))}
    </ul>
  );
}
