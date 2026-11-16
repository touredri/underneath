import { Badge, Button, cn } from '../components/ui/kit';

export function Page8({ onOpen }) {
  return (
    <section className={cn('page', 'page-8')}>
      <Badge tone="info">Page 8</Badge>
      <Button onClick={onOpen}>Open</Button>
    </section>
  );
}
