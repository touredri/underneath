import { Badge, Button, cn } from '../components/ui/kit';

export function Page5({ onOpen }) {
  return (
    <section className={cn('page', 'page-5')}>
      <Badge tone="info">Page 5</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
