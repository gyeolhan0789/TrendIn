import { toneOf } from '../trendFormat';

/** 분야를 색 있는 작은 조각으로 보여 줍니다. 트렌드 탐색 카드와 관심 키워드 표가 함께 씁니다. */
export function TagChip({ label }: { label: string }) {
  return <span className={`trendin-tag trendin-tag--${toneOf(label)}`}>{label}</span>;
}
