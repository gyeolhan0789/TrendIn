import { useEffect, useState } from 'react';

/**
 * 글자를 칠 때마다가 아니라, 잠시 멈춘 뒤의 값만 돌려줍니다.
 * 검색 상자마다 같은 타이머를 따로 두고 있어 한곳으로 모았습니다.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  return settled;
}
