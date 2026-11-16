import { Badge, Button, cn } from '../components/ui/kit';

export function Page12({ onOpen }) {
  return (
    <section className={cn('page', 'page-12')}>
      <Badge tone="info">Page 12</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
