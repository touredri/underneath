import { Badge, Button, cn } from '../components/ui/kit';

export function Page7({ onOpen }) {
  return (
    <section className={cn('page', 'page-7')}>
      <Badge tone="info">Page 7</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
