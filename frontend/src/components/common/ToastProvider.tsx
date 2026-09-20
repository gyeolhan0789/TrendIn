import { useEffect, useRef, useState } from 'react';
import type { PropsWithChildren } from 'react';
import type { ToastDetail, ToastType } from './toast';

/** 쪽지가 떠 있는 시간입니다. */
const TOAST_LIFE_MS = 3_000;

/* 성공과 실패를 글자색 대신 왼쪽 칩으로 가릅니다. 쪽지 글은 두 경우 모두 잉크색이라 읽기가 같습니다. */
function ToastMark({ type }: { type: ToastType }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {type === 'error' ? <path d="M12 7v6M12 17h.01" /> : <path d="m5 13 4 4L19 7" />}
    </svg>
  );
}

export function ToastProvider({ children }: PropsWithChildren) {
  /*
   * seq 는 몇 번째 쪽지인지입니다. 글이 같은 쪽지가 잇따라 오면(키워드를 뺐다가 다시 빼는 식)
   * React 가 같은 상자를 그대로 두어 등장 움직임이 다시 돌지 않고, 새 쪽지가 온 줄 모릅니다.
   * key 로 걸어 상자를 새로 세웁니다.
   */
  const [toast, setToast] = useState<(ToastDetail & { seq: number }) | null>(null);
  const hideTimer = useRef(0);
  const seq = useRef(0);

  useEffect(() => {
    const handleToast = (event: Event) => {
      seq.current += 1;
      setToast({ ...(event as CustomEvent<ToastDetail>).detail, seq: seq.current });
      /*
       * 앞 쪽지의 타이머를 걷고 다시 겁니다. 그대로 두면 온보딩에서 키워드를 연달아 담을 때처럼
       * 쪽지가 잇따를 때, 먼저 걸린 타이머가 방금 뜬 쪽지를 3초가 되기 전에 지웁니다.
       */
      window.clearTimeout(hideTimer.current);
      hideTimer.current = window.setTimeout(() => setToast(null), TOAST_LIFE_MS);
    };

    window.addEventListener('app:toast', handleToast);
    return () => {
      window.removeEventListener('app:toast', handleToast);
      window.clearTimeout(hideTimer.current);
    };
  }, []);

  return (
    <>
      {children}
      {toast && (
        <div key={toast.seq} className={`toast toast--${toast.type ?? 'success'}`} role="status">
          <span className="toast-mark" aria-hidden="true"><ToastMark type={toast.type ?? 'success'} /></span>
          <span>{toast.message}</span>
        </div>
      )}
    </>
  );
}
