/*
 * 리포트 화면이 쓰는 표본 자료입니다.
 *
 * 백엔드에는 아직 리포트 API가 없습니다. 리포트를 만들어 두고 다시 꺼내 보는 기능 자체가 없어서,
 * '생성된 리포트' 목록과 '빠른 리포트' 갈래는 서버에서 온 값이 아니라 화면 모양을 잡기 위해 적어 둔
 * 표본이고, 화면에도 표본이라고 밝혀 둡니다. API가 생기면 이 파일만 걷어내고 같은 모양의 응답으로
 * 갈아 끼웁니다.
 *
 * 화면 위쪽 '주간 트렌드 리포트' 칸은 표본이 아닙니다. 트렌드 목록 API에서 받은 실제 집계로 그립니다.
 */

/** 시안의 거르개 칸이 고르는 리포트 갈래입니다. */
export const REPORT_KINDS = ['WEEKLY', 'ISSUE', 'CATEGORY', 'CUSTOM'] as const;

export type ReportKind = (typeof REPORT_KINDS)[number];

/** 갈래마다 이름과 색을 함께 둡니다. 태그와 거르개 칸이 같은 이름을 씁니다. */
export const REPORT_KIND_LABELS: Record<ReportKind, string> = {
  WEEKLY: '주간 리포트',
  ISSUE: '이슈 리포트',
  CATEGORY: '카테고리 리포트',
  CUSTOM: '맞춤 리포트',
};

/** 시안의 태그 색. 갈래가 넷뿐이라 이름과 함께 여기서 짝지어 둡니다. */
export const REPORT_KIND_TONES: Record<ReportKind, string> = {
  WEEKLY: 'indigo',
  ISSUE: 'rose',
  CATEGORY: 'blue',
  CUSTOM: 'emerald',
};

export interface SampleReport {
  id: string;
  kind: ReportKind;
  title: string;
  summary: string;
  /** 만든 날. 화면은 이 값을 '2026. 9. 14' 모양으로 풀어 씁니다. */
  createdOn: string;
  /** 리포트가 담은 구간. 서버가 기간을 코드로 주므로 표본도 같은 말로 적습니다. */
  period: string;
}

/*
 * 날짜는 오늘을 기준으로 계산하지 않고 박아 둡니다. 오늘에 맞춰 움직이면 표본이 실제 기록처럼
 * 보입니다. 표본은 표본으로 읽히는 편이 낫습니다.
 */
export const SAMPLE_REPORTS: SampleReport[] = [
  { id: 'r-01', kind: 'WEEKLY', title: 'AI 브라우저 주간 분석', summary: 'AI 브라우저 관련 최신 트렌드 분석 리포트', createdOn: '2026-09-14', period: '최근 7일' },
  { id: 'r-02', kind: 'ISSUE', title: '아이폰17 이슈 변화', summary: '아이폰17 관련 언급량 및 반응 분석', createdOn: '2026-09-13', period: '최근 7일' },
  { id: 'r-03', kind: 'CATEGORY', title: '추석 소비 트렌드', summary: '추석 시즌 소비 트렌드 종합 분석', createdOn: '2026-09-11', period: '최근 30일' },
  { id: 'r-04', kind: 'CUSTOM', title: '여행 일본 트렌드 분석', summary: '일본 여행 관련 키워드 및 콘텐츠 흐름', createdOn: '2026-09-09', period: '최근 14일' },
  { id: 'r-05', kind: 'ISSUE', title: '부동산 규제 이슈 분석', summary: '최신 부동산 규제 관련 여론 및 반응', createdOn: '2026-09-07', period: '최근 7일' },
  { id: 'r-06', kind: 'WEEKLY', title: '9월 첫째 주 트렌드 요약', summary: '한 주 동안 가장 크게 오른 키워드 모음', createdOn: '2026-09-05', period: '최근 7일' },
  { id: 'r-07', kind: 'CATEGORY', title: '스포츠 카테고리 비교', summary: '스포츠 분야 안에서 갈래별 언급량 비교', createdOn: '2026-09-02', period: '최근 30일' },
  { id: 'r-08', kind: 'CUSTOM', title: '관심 키워드 월간 묶음', summary: '등록한 관심 키워드의 한 달 흐름 정리', createdOn: '2026-08-31', period: '최근 30일' },
  { id: 'r-09', kind: 'WEEKLY', title: '8월 마지막 주 트렌드 요약', summary: '주간 상위 키워드와 새로 등장한 키워드', createdOn: '2026-08-29', period: '최근 7일' },
];

/*
 * 시안의 '빠른 리포트' 갈래입니다. 누르면 그 자리에서 리포트가 만들어져야 하는데 받아 줄 API가
 * 없어, 자리는 그대로 두고 아직 누를 수 없다는 것만 표시합니다.
 */
export const QUICK_REPORTS: { icon: string; tone: string; label: string }[] = [
  { icon: '📊', tone: 'indigo', label: '주간 트렌드 리포트' },
  { icon: '🔍', tone: 'blue', label: '특정 키워드 심층 분석' },
  { icon: '📈', tone: 'emerald', label: '카테고리 비교 리포트' },
  { icon: '💬', tone: 'amber', label: '플랫폼별 반응 분석' },
];
