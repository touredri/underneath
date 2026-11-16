import { Badge, Button, cn } from '../components/ui/kit';

export function Page10({ onOpen }) {
  return (
    <section className={cn('page', 'page-10')}>
      <Badge tone="info">Page 10</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
