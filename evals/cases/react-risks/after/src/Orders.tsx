import { useEffect, useState } from 'react';

export const x = 1;

export function OrderCount({ orders }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    setCount(orders.length);
  });
  return <p>{count}</p>;
}

export function OrderList({ userId }) {
  const [orders, setOrders] = useState([]);
  useEffect(async () => {
    const res = await fetch(`/api/orders?user=${userId}`);
    setOrders(await res.json());
  }, [userId]);
  return (
    <ul>
      {orders.map((order, index) => (
        <li key={index}>{order.label}</li>
      ))}
    </ul>
  );
}

export async function archiveAll(orders) {
  orders.forEach(async (order) => {
    await fetch(`/api/orders/${order.id}/archive`, { method: 'POST' });
  });
  try {
    localStorage.removeItem('orders');
  } catch (e) {}
}
