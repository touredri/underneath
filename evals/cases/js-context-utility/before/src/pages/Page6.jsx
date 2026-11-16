import { Badge, Button, cn } from '../components/ui/kit';

export function Page6({ onOpen }) {
  return (
    <section className={cn('page', 'page-6')}>
      <Badge tone="info">Page 6</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
