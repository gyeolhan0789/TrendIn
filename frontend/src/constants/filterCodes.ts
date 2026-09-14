/**
 * 트렌드 조회에 쓰는 코드 값입니다. 화면이 쓰는 표기와 서버가 받는 값이 달라 여기서 맞춥니다.
 *
 * 기간은 서버 enum(AnalysisPeriod)과 1:1이고 목록을 내려주는 API가 없어 여기에 적어 둡니다.
 * 분야는 반대로 GET /domains 가 알려주므로 코드를 박아 두지 않고, 받은 목록에 맞춰 고르기만 합니다.
 */

export const ANALYSIS_PERIODS = ['24H', '7D', '30D'] as const;

export type PeriodCode = (typeof ANALYSIS_PERIODS)[number];

export const DEFAULT_PERIOD: PeriodCode = '24H';

export function isPeriodCode(value: string): value is PeriodCode {
  return (ANALYSIS_PERIODS as readonly string[]).includes(value);
}

/**
 * 주소창의 기간 값을 서버가 받는 코드로 바꿉니다.
 * 예전 링크가 소문자(24h)로 남아 있을 수 있어 대소문자를 가리지 않고, 모르는 값은 기본값으로 둡니다.
 */
export function parsePeriod(raw: string | null | undefined): PeriodCode {
  const normalized = raw?.trim().toUpperCase() ?? '';
  return isPeriodCode(normalized) ? normalized : DEFAULT_PERIOD;
}

/** 서버 enum 은 대소문자를 그대로 보므로 분야 코드는 항상 대문자로 보냅니다. */
export function normalizeDomainCode(raw: string | null | undefined): string {
  return raw?.trim().toUpperCase() ?? '';
}

/**
 * 주소창의 분야 값을 실제로 고를 수 있는 분야 중 하나로 맞춥니다.
 * 값이 없거나 목록에 없는 분야면 첫 번째 분야를 씁니다. 목록이 아직 비었으면 고를 수 없으므로 undefined 입니다.
 */
export function resolveDomainCode(
  raw: string | null | undefined,
  options: readonly { domain: string }[],
): string | undefined {
  const normalized = normalizeDomainCode(raw);
  return options.find((option) => option.domain === normalized)?.domain ?? options[0]?.domain;
}
