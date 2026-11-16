import { Badge, Button, cn } from '../components/ui/kit';

export function Page1({ onOpen }) {
  return (
    <section className={cn('page', 'page-1')}>
      <Badge tone="info">Page 1</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
