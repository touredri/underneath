import { memo, useCallback, useMemo, useRef, useState } from 'react';

const ProductRow = memo(function ProductRow({ product, onSelect }) {
  return <li onClick={() => onSelect(product.id)}>{product.name}</li>;
});

export function Products({ items }) {
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState(null);
  const input = useRef(null);
  const visible = useMemo(
    () => items.filter((p) => p.name.toLowerCase().includes(filter.toLowerCase())),
    [items, filter],
  );
  const select = useCallback((id) => {
    setSelected(id);
    input.current?.focus();
  }, []);
  return (
    <div>
      <input ref={input} value={filter} onChange={(e) => setFilter(e.target.value)} />
      <ul>
        {visible.map((p) => (
          <ProductRow key={p.id} product={p} onSelect={select} />
        ))}
      </ul>
      {selected && <p>Selected {selected}</p>}
    </div>
  );
}
