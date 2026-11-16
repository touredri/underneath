import { Badge, Button, cn } from '../components/ui/kit';
import { discountLabel, formatTotal } from './money';

export function OrderSummary({ order, onPay }) {
  const late = order.dueDate < Date.now();
  return (
    <div className={cn('summary', late && 'summary-late')}>
      <p>{order.id}: {formatTotal(order.totalCents)} {discountLabel(order.discount)}</p>
      {late && <Badge tone="warn">Late</Badge>}
      <Button primary onClick={() => onPay(order.id)}>Pay</Button>
    </div>
  );
}
