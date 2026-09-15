/* 태그마다 색을 달리 해 한눈에 구분됩니다. 이름을 자릿수로 접어 고르므로 같은 분야는 늘 같은 색이 나옵니다. */
export const tagTones = ['indigo', 'rose', 'emerald', 'violet', 'amber'] as const;

export type TagTone = (typeof tagTones)[number];

export function toneOf(label: string): TagTone {
  const sum = Array.from(label).reduce((total, char) => total + char.charCodeAt(0), 0);
  return tagTones[sum % tagTones.length];
}

/** 12.4만처럼 짧게 읽히게 줄입니다. */
export function formatCount(count: number) {
  if (count >= 10_000) return `${(count / 10_000).toFixed(1)}만`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}천`;
  return count.toLocaleString();
}

/** 이전 구간 언급량이 없으면 서버가 증가율을 비워 둡니다. 그 자리에 숫자를 지어내지 않습니다. */
export function formatGrowth(growthRate: number | null) {
  if (growthRate === null) return '—';
  return `${growthRate > 0 ? '+' : ''}${growthRate}%`;
}
