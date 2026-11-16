import type { User } from "../components/UserList";

export async function searchUsers(query: string, signal: AbortSignal): Promise<User[]> {
  const res = await fetch(`/api/users?q=${encodeURIComponent(query)}`, { signal });
  if (!res.ok) {
    throw new Error(`Search failed: ${res.status}`);
  }
  return res.json();
}
