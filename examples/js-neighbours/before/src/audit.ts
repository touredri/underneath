// Each of these files defines its own log(): the name alone cannot say which one a call means.
export function log(message: string) {
  console.log('[audit]', message);
}

export function auditSummary(rows: string[]) {
  log(`${rows.length} audit`);
  return rows.slice(0, 10);
}
