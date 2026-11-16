import { useMemo, useState } from 'react';

export function Profile({ user, orders }) {
  const [tab, setTab] = useState('orders');
  const total = useMemo(() => orders.reduce((sum, o) => sum + o.amount, 0), [orders]);
  return (
    <section>
      <h2>{user.name}</h2>
      <button onClick={() => setTab('orders')}>Orders ({total})</button>
      {tab === 'orders' && <p>{orders.length} orders</p>}
    </section>
  );
}
