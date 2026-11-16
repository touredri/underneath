// Each of these files defines its own log(): the name alone cannot say which one a call means.
export function log(message: string) {
  console.log('[billing]', message);
}

export function billingSummary(rows: string[]) {
  log(`${rows.length} billing`);
  return rows.slice(0, 10);
}
