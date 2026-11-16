import { useEffect, useState } from 'react';
import { getJson } from './api';

export async function loadDashboard(userId) {
  try {
    const [orders, stock] = await Promise.all([
      getJson(`/api/orders?user=${userId}`),
      getJson('/api/stock'),
    ]);
    return { orders, stock };
  } catch (err) {
    return { orders: [], stock: [], error: String(err) };
  }
}

export function usePolling(load, everyMs) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let alive = true;
    const tick = () => load().then((d) => alive && setData(d));
    tick();
    const id = setInterval(tick, everyMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [load, everyMs]);
  return data;
}
