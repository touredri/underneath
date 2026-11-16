export function formatPrice(cents: number): string {
  return `${(cents / 100).toFixed(2)} €`;
}

export function roundCents(value: number): number {
  return Math.round(value);
}
