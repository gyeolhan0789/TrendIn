interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = '데이터를 불러오지 못했습니다.', onRetry }: ErrorStateProps) {
  return (
    <div className="state-box" role="alert">
      <p>{message}</p>
      {onRetry && <button type="button" onClick={onRetry}>다시 시도</button>}
    </div>
  );
}

