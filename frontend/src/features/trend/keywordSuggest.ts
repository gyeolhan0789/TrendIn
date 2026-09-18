/**
 * 검색어와 겹치는 자리를 앞·겹친 곳·뒤 세 도막으로 나눕니다.
 * 서버가 대소문자를 가리지 않고 찾아 주므로 여기서도 가리지 않습니다.
 */
export function splitMatch(text: string, query: string): [string, string, string] {
  const at = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
  if (at < 0) return [text, '', ''];
  return [text.slice(0, at), text.slice(at, at + query.length), text.slice(at + query.length)];
}

