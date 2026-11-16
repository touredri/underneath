import { useEffect, useState } from 'react';

export function Search({ onPick }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/search?q=${query}`, { signal: controller.signal })
      .then((r) => r.json())
      .then(setResults);
    return () => controller.abort();
  }, [query]);

  return (
    <div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      <ul>
        {results.map((r) => (
          <li key={r.id} onClick={() => onPick(r)}>{r.name}</li>
        ))}
      </ul>
    </div>
  );
}
