export function cn(...names) {
  return names.filter(Boolean).join(' ');
}

export function Button({ children, onClick, primary }) {
  return <button className={cn('btn', primary && 'btn-primary')} onClick={onClick}>{children}</button>;
}

export function Badge({ children, tone }) {
  return <span className={cn('badge', tone && `badge-${tone}`)}>{children}</span>;
}
