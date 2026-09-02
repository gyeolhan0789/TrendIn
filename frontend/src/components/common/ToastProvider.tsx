import { useEffect, useState } from 'react';
import type { PropsWithChildren } from 'react';
import type { ToastDetail } from './toast';

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
      {toast && <div className={`toast toast--${toast.type ?? 'success'}`} role="status">{toast.message}</div>}
    </>
  );
}
