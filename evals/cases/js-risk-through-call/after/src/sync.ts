import { useEffect, useState } from 'react';

export const VERSION = 1;

export async function saveItem(item) {
  await fetch(`/api/items/${item.id}`, { method: 'PUT', body: JSON.stringify(item) });
}

export function logItem(item) {
  console.log(item.id);
}

export function syncAll(items) {
  items.forEach(saveItem);
  items.forEach(logItem);
}

export function Counter({ items }) {
  const [count, setCount] = useState(0);
  const recount = () => setCount(items.length);
  const report = () => console.log(count);
  useEffect(() => {
    recount();
  });
  useEffect(() => {
    report();
  });
  return <p>{count}</p>;
}
