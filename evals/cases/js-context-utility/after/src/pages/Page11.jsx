import { Badge, Button, cn } from '../components/ui/kit';

export function Page11({ onOpen }) {
  return (
    <section className={cn('page', 'page-11')}>
      <Badge tone="info">Page 11</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
