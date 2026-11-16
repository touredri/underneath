import { Badge, Button, cn } from '../components/ui/kit';

export function Page4({ onOpen }) {
  return (
    <section className={cn('page', 'page-4')}>
      <Badge tone="info">Page 4</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
