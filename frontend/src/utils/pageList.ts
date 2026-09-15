/**
 * 쪽 번호 줄에 세울 항목입니다. 1쪽과 마지막 쪽은 늘 보이고, 현재 쪽 둘레만 이어 붙입니다.
 * 사이가 끊기는 자리는 'gap' 으로 표시해 화면이 …로 접습니다.
 *
 * 트렌드 탐색과 저장된 트렌드가 같은 모양의 쪽 번호를 써서 여기에 둡니다.
 */
export function pageList(current: number, total: number) {
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const shown = [...pages].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b);
  const out: (number | 'gap')[] = [];
  shown.forEach((page, index) => {
    if (index > 0 && page - shown[index - 1] > 1) out.push('gap');
    out.push(page);
  });
  return out;
}
