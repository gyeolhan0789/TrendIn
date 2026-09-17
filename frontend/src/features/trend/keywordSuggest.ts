/**
 * 위아래 키로 옮겨 갈 다음 자리입니다. -1 은 아무 줄도 고르지 않은 상태이고,
 * 끝에 닿으면 반대쪽 끝으로 돕니다. 고를 줄이 없으면 고르지 않은 채로 둡니다.
 */
export function nextSuggestIndex(current: number, length: number, down: boolean): number {
  if (length === 0) return -1;
  if (current < 0) return down ? 0 : length - 1;
  return (current + (down ? 1 : -1) + length) % length;
}

/**
 * 검색어와 겹치는 자리를 앞·겹친 곳·뒤 세 도막으로 나눕니다.
 * 서버가 대소문자를 가리지 않고 찾아 주므로 여기서도 가리지 않습니다.
 */
export function splitMatch(text: string, query: string): [string, string, string] {
  const at = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
  if (at < 0) return [text, '', ''];
  return [text.slice(0, at), text.slice(at, at + query.length), text.slice(at + query.length)];
}

