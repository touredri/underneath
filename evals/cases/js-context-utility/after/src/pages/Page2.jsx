import { Badge, Button, cn } from '../components/ui/kit';

export function Page2({ onOpen }) {
  return (
    <section className={cn('page', 'page-2')}>
      <Badge tone="info">Page 2</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
