import { emptyCart } from './cart';

export function startCheckout() {
  const cart = emptyCart();
  return { cart, step: 'address' };
}
