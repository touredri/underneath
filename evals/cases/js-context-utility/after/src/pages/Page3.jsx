import { Badge, Button, cn } from '../components/ui/kit';

export function Page3({ onOpen }) {
  return (
    <section className={cn('page', 'page-3')}>
      <Badge tone="info">Page 3</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
