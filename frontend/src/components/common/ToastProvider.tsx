import { useEffect, useState } from 'react';
import type { PropsWithChildren } from 'react';
import type { ToastDetail, ToastType } from './toast';

/* 성공과 실패를 글자색 대신 왼쪽 칩으로 가릅니다. 쪽지 글은 두 경우 모두 잉크색이라 읽기가 같습니다. */
function ToastMark({ type }: { type: ToastType }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {type === 'error' ? <path d="M12 7v6M12 17h.01" /> : <path d="m5 13 4 4L19 7" />}
    </svg>
  );
}

export function ToastProvider({ children }: PropsWithChildren) {
  const [toast, setToast] = useState<ToastDetail | null>(null);

  useEffect(() => {
    const handleToast = (event: Event) => {
      setToast((event as CustomEvent<ToastDetail>).detail);
      window.setTimeout(() => setToast(null), 3_000);
    };

    window.addEventListener('app:toast', handleToast);
    return () => window.removeEventListener('app:toast', handleToast);
  }, []);

  return (
    <>
      {children}
      {toast && (
        <div className={`toast toast--${toast.type ?? 'success'}`} role="status">
          <span className="toast-mark" aria-hidden="true"><ToastMark type={toast.type ?? 'success'} /></span>
          <span>{toast.message}</span>
        </div>
      )}
    </>
  );
}
