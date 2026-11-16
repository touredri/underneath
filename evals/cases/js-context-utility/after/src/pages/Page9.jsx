import { Badge, Button, cn } from '../components/ui/kit';

export function Page9({ onOpen }) {
  return (
    <section className={cn('page', 'page-9')}>
      <Badge tone="info">Page 9</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
