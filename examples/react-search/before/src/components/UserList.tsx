export type User = { id: number; name: string; joinedAt: string };

export function UserList({ users }: { users: User[] }) {
  if (users.length === 0) return <p>No users yet.</p>;
  return (
    <ul>
      {users.map((u) => (
        <li key={u.id}>{u.name}</li>
      ))}
    </ul>
  );
}
