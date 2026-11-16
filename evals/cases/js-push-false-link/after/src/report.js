import { Queue } from './queue';

export const jobs = new Queue();

export function lateOrders(orders, today) {
  const late = [];
  for (const o of orders) {
    if (o.due < today) late.push(o.id);
  }
  return late;
}
