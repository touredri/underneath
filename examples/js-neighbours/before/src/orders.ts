// Each of these files defines its own log(): the name alone cannot say which one a call means.
export function log(message: string) {
  console.log('[orders]', message);
}

export function ordersSummary(rows: string[]) {
  log(`${rows.length} orders`);
  return rows.slice(0, 10);
}
