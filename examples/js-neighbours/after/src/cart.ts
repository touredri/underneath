import { formatPrice } from './money';

export function emptyCart() {
  return { items: [], total: 0 };
}

export function addItem(cart, item) {
  const items = [...cart.items, item];
  const total = items.reduce((sum, i) => sum + i.price * i.qty, 0);
  log(`added ${item.id}`);
  return { items, total, label: formatPrice(total) };
}
