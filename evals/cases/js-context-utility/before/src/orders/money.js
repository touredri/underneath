export function formatTotal(cents) {
  return `${(cents / 100).toFixed(2)} €`;
}

export function discountLabel(percent) {
  return percent > 0 ? `-${percent}%` : '';
}
