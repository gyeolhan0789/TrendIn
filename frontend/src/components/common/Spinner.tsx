interface SpinnerProps {
  size?: 'small' | 'medium';
}

export function Spinner({ size = 'medium' }: SpinnerProps) {
  return <span className={`spinner spinner--${size}`} role="status" aria-label="처리 중" />;
}

