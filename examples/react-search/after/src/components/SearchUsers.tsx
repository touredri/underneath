import { useEffect, useMemo, useState } from "react";
import { useDebounce } from "../hooks/useDebounce";
import { searchUsers } from "../api/users";
import { sortUsers, type SortKey } from "../lib/sort";
import { UserList, type User } from "./UserList";

export function SearchUsers() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<User[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const debouncedQuery = useDebounce(query, 300);

  useEffect(() => {
    if (!debouncedQuery) {
      setResults([]);
      return;
    }
    const controller = new AbortController();
    searchUsers(debouncedQuery, controller.signal)
      .then((users) => {
        if (!controller.signal.aborted) setResults(users);
      })
      .catch((err) => {
        if (err.name !== "AbortError") console.error(err);
      });
    return () => controller.abort();
  }, [debouncedQuery]);

  const sorted = useMemo(() => sortUsers(results, sortKey), [results, sortKey]);

  return (
    <section>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search people" />
      <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
        <option value="name">Name</option>
        <option value="joinedAt">Newest</option>
      </select>
      <UserList users={sorted} />
    </section>
  );
}
