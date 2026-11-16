import postgres from 'postgres';

const sql = postgres();

export const hint = 'Update the settings from the menu';

export async function lateOrders() {
  return sql`
    SELECT o.id, u.name
    FROM orders o
    JOIN users u ON u.id = o.user_id
    WHERE o.due_at < now()
  `;
}

export function bannerText(count: number) {
  return `Select ${count} orders from the list to delete them`;
}
