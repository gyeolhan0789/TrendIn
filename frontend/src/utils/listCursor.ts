/**
 * 위아래 키로 옮겨 갈 다음 자리입니다. -1 은 아무 줄도 고르지 않은 상태이고,
 * 끝에 닿으면 반대쪽 끝으로 돕니다. 고를 줄이 없으면 고르지 않은 채로 둡니다.
 *
 * 검색어 목록과 드롭다운 목록이 같은 규칙으로 움직이도록 한곳에 둡니다.
 */
export function nextIndex(current: number, length: number, down: boolean): number {
  if (length === 0) return -1;
  if (current < 0) return down ? 0 : length - 1;
  return (current + (down ? 1 : -1) + length) % length;
}
