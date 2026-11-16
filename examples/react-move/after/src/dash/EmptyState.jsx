export function EmptyState({ message, onRetry }) {
  return (
    <div className="empty-state">
      <p>{message}</p>
      <button type="button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
