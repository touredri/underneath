import type { User } from "../components/UserList";

export type SortKey = "name" | "joinedAt";

export function sortUsers(users: User[], key: SortKey): User[] {
  return [...users].sort((a, b) =>
    key === "name" ? a.name.localeCompare(b.name) : b.joinedAt.localeCompare(a.joinedAt)
  );
}
