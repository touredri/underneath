import { useEffect, useState } from 'react';

export const x = 1;

export function OrderCount({ orders }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    setCount(orders.length);
  }, [orders]);
  useEffect(() => {
    document.title = `${count} orders`;
  });
  return <p>{count}</p>;
}

export function OrderList({ userId }) {
  const [orders, setOrders] = useState([]);
  useEffect(() => {
    const load = async () => {
      const res = await fetch(`/api/orders?user=${userId}`);
      setOrders(await res.json());
    };
    load();
  }, [userId]);
  return (
    <ul>
      {orders.map((order) => (
        <li key={order.id}>{order.label}</li>
      ))}
    </ul>
  );
}

export async function archiveAll(orders) {
  for (const order of orders) {
    await fetch(`/api/orders/${order.id}/archive`, { method: 'POST' });
  }
  try {
    localStorage.removeItem('orders');
  } catch (e) {
    // private mode: nothing to clear
  }
}
