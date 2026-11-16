// Each of these files defines its own log(): the name alone cannot say which one a call means.
export function log(message: string) {
  console.log('[users]', message);
}

export function usersSummary(rows: string[]) {
  log(`${rows.length} users`);
  return rows.slice(0, 10);
}
