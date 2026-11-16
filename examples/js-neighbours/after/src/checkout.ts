import { addItem, emptyCart } from './cart';

export function startCheckout(firstItem) {
  const cart = addItem(emptyCart(), firstItem);
  return { cart, step: 'address' };
}
