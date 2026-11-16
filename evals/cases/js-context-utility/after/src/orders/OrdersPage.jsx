import { OrderSummary } from './OrderSummary';

export function OrdersPage({ order }) {
  return <main><OrderSummary order={order} /></main>;
}
