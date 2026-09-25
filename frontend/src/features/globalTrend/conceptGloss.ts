/**
 * 키워드 원문 옆에 덧붙일 영어 이름을 고릅니다. 붙일 것이 없으면 null 입니다.
 *
 * 나라별 키워드는 기사에 적힌 원문이라 이탈리아에서는 pelle, 한국에서는 가죽처럼 나라마다 언어가
 * 다릅니다. 서버가 개념의 대표 이름(영어)을 함께 주면 그것을 괄호로 붙여 읽히게 합니다.
 * 원문과 철자가 같으면(leather) 같은 말을 두 번 적게 되므로 붙이지 않습니다.
 */
export function conceptGloss(keyword: string, conceptName: string | null | undefined): string | null {
  const name = conceptName?.trim();
  if (!name) return null;
  if (name.toLowerCase() === keyword.trim().toLowerCase()) return null;
  return name;
}

export function countryTrendLabel(
  countryCode: string,
  keyword: string,
  conceptName: string | null | undefined,
): string {
  const gloss = conceptGloss(keyword, conceptName);
  return countryCode === 'KR' || !gloss ? keyword : gloss;
}
