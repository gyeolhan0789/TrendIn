interface EmptyStateProps {
  message?: string;
}

export function EmptyState({ message = '표시할 데이터가 없습니다.' }: EmptyStateProps) {
  return <div className="state-box"><p>{message}</p></div>;
}

