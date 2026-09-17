/*
 * 국가별 트렌드 화면이 쓰는 표본 자료입니다.
 *
 * 백엔드에는 아직 나라별 집계 API가 없습니다. 그래서 이 화면의 나라 수치는 서버에서 온 값이 아니라
 * 화면 모양을 잡기 위해 적어 둔 표본이고, 화면에도 '표본 자료'라고 밝혀 둡니다. API가 생기면
 * 이 파일만 걷어내고 같은 모양의 응답으로 갈아 끼웁니다.
 *
 * 나라의 경위도와 ISO 코드는 표본이 아니라 실제 값입니다. 지도가 엉뚱한 자리를 가리키면 안 됩니다.
 */

export interface Country {
  code: string;
  /** world-atlas 가 쓰는 ISO 3166-1 숫자 코드. 지도에서 그 나라를 찾는 열쇠입니다. */
  atlasId: string;
  name: string;
  flag: string;
  lon: number;
  lat: number;
}

export const COUNTRIES: Record<string, Country> = {
  KR: { code: 'KR', atlasId: '410', name: '대한민국', flag: '🇰🇷', lon: 127.8, lat: 36.5 },
  JP: { code: 'JP', atlasId: '392', name: '일본', flag: '🇯🇵', lon: 138.0, lat: 37.0 },
  CN: { code: 'CN', atlasId: '156', name: '중국', flag: '🇨🇳', lon: 104.0, lat: 35.0 },
  VN: { code: 'VN', atlasId: '704', name: '베트남', flag: '🇻🇳', lon: 106.0, lat: 16.0 },
  TH: { code: 'TH', atlasId: '764', name: '태국', flag: '🇹🇭', lon: 101.0, lat: 15.5 },
  ID: { code: 'ID', atlasId: '360', name: '인도네시아', flag: '🇮🇩', lon: 117.0, lat: -2.0 },
  IN: { code: 'IN', atlasId: '356', name: '인도', flag: '🇮🇳', lon: 79.0, lat: 22.0 },
  AU: { code: 'AU', atlasId: '036', name: '호주', flag: '🇦🇺', lon: 134.0, lat: -25.0 },
  GB: { code: 'GB', atlasId: '826', name: '영국', flag: '🇬🇧', lon: -2.0, lat: 54.0 },
  FR: { code: 'FR', atlasId: '250', name: '프랑스', flag: '🇫🇷', lon: 2.5, lat: 46.5 },
  DE: { code: 'DE', atlasId: '276', name: '독일', flag: '🇩🇪', lon: 10.5, lat: 51.2 },
  IT: { code: 'IT', atlasId: '380', name: '이탈리아', flag: '🇮🇹', lon: 12.5, lat: 42.5 },
  ES: { code: 'ES', atlasId: '724', name: '스페인', flag: '🇪🇸', lon: -3.7, lat: 40.3 },
  US: { code: 'US', atlasId: '840', name: '미국', flag: '🇺🇸', lon: -98.0, lat: 39.5 },
  CA: { code: 'CA', atlasId: '124', name: '캐나다', flag: '🇨🇦', lon: -106.0, lat: 56.0 },
  MX: { code: 'MX', atlasId: '484', name: '멕시코', flag: '🇲🇽', lon: -102.0, lat: 23.5 },
  BR: { code: 'BR', atlasId: '076', name: '브라질', flag: '🇧🇷', lon: -51.0, lat: -12.0 },
  AE: { code: 'AE', atlasId: '784', name: '아랍에미리트', flag: '🇦🇪', lon: 54.0, lat: 24.0 },
};

/** 트렌드가 한 나라에서 뜬 자취. 배열 순서가 곧 퍼져 나간 순서입니다. */
export interface SpreadStop {
  country: string;
  /** 그 나라에서 처음 눈에 띈 날 */
  since: string;
  growth: number;
  mentions: number;
}

export interface GlobalTrend {
  id: string;
  keyword: string;
  domain: string;
  emoji: string;
  since: string;
  growth: number;
  mentions: number;
  contents: number;
  /** 언급이 잡힌 나라 수. 아래 spread 는 그중 흐름이 뚜렷한 곳만 추린 것입니다. */
  countries: number;
  summary: string;
  /** 오른쪽 그래프가 쓰는 관심도 추이. 값 하나가 하루입니다. */
  history: number[];
  spread: SpreadStop[];
}

/*
 * 분야는 서버가 가르는 두 갈래(개발·패션)뿐입니다. 없는 분야를 화면에만 세워 두면
 * 자료를 붙이는 날 지워야 하므로, 표본도 이 둘로만 만듭니다.
 */
export const GLOBAL_TRENDS: GlobalTrend[] = [
  {
    id: 'ai-coding-agent',
    keyword: 'AI 코딩 에이전트',
    domain: '개발',
    emoji: '🤖',
    since: '2025.08.02',
    growth: 128.4,
    mentions: 1580400,
    contents: 41230,
    countries: 112,
    summary: '샌프란시스코에서 뜬 뒤 런던과 벵갈루루를 거쳐 서울까지 왔습니다.',
    history: [38, 41, 44, 43, 49, 55, 58, 62, 66, 71, 75, 82, 88, 97, 104, 112, 121, 128],
    spread: [
      { country: 'US', since: '08.02', growth: 128.4, mentions: 486000 },
      { country: 'GB', since: '08.09', growth: 94.6, mentions: 233000 },
      { country: 'IN', since: '08.14', growth: 78.8, mentions: 298000 },
      { country: 'DE', since: '08.19', growth: 51.2, mentions: 171000 },
      { country: 'KR', since: '08.25', growth: 47.4, mentions: 142000 },
    ],
  },
  {
    id: 'neo-vintage',
    keyword: 'Neo Vintage',
    domain: '패션',
    emoji: '👔',
    since: '2025.08.20',
    growth: 96.2,
    mentions: 1234567,
    contents: 32548,
    countries: 76,
    summary: '서울에서 뜬 뒤 도쿄와 런던을 거쳐 파리·상파울루로 이어지고 있습니다.',
    history: [30, 33, 36, 35, 40, 45, 48, 52, 56, 60, 64, 70, 75, 80, 85, 89, 93, 96],
    spread: [
      { country: 'KR', since: '08.20', growth: 96.2, mentions: 412000 },
      { country: 'JP', since: '08.23', growth: 83.2, mentions: 268000 },
      { country: 'GB', since: '08.27', growth: 72.1, mentions: 191000 },
      { country: 'FR', since: '08.30', growth: 61.3, mentions: 148000 },
      { country: 'BR', since: '09.01', growth: 28.5, mentions: 92000 },
    ],
  },
  {
    id: 'rust-adoption',
    keyword: '러스트 도입',
    domain: '개발',
    emoji: '🦀',
    since: '2025.08.06',
    growth: 74.1,
    mentions: 861200,
    contents: 21870,
    countries: 54,
    summary: '베를린의 인프라 팀에서 시작해 미국과 일본의 백엔드 이야기로 번졌습니다.',
    history: [22, 26, 31, 35, 34, 38, 42, 44, 47, 51, 55, 58, 62, 65, 68, 70, 72, 74],
    spread: [
      { country: 'DE', since: '08.06', growth: 74.1, mentions: 214000 },
      { country: 'US', since: '08.11', growth: 66.4, mentions: 187000 },
      { country: 'JP', since: '08.18', growth: 51.8, mentions: 162000 },
      { country: 'KR', since: '08.24', growth: 43.2, mentions: 121000 },
    ],
  },
  {
    id: 'quiet-luxury',
    keyword: '조용한 럭셔리',
    domain: '패션',
    emoji: '🧥',
    since: '2025.08.14',
    growth: 62.8,
    mentions: 742900,
    contents: 19640,
    countries: 48,
    summary: '밀라노와 파리에서 시작해 뉴욕과 서울로 넘어왔습니다.',
    history: [20, 23, 27, 30, 29, 33, 36, 39, 42, 45, 48, 51, 54, 56, 58, 60, 61, 62],
    spread: [
      { country: 'IT', since: '08.14', growth: 62.8, mentions: 198000 },
      { country: 'FR', since: '08.17', growth: 57.4, mentions: 174000 },
      { country: 'US', since: '08.22', growth: 44.1, mentions: 152000 },
      { country: 'KR', since: '08.28', growth: 36.5, mentions: 113000 },
    ],
  },
  {
    id: 'rag-pipeline',
    keyword: 'RAG 파이프라인',
    domain: '개발',
    emoji: '🧩',
    since: '2025.08.08',
    growth: 52.3,
    mentions: 1042300,
    contents: 28410,
    countries: 88,
    summary: '미국에서 먼저 달아오른 뒤 인도와 한국의 실무 글로 옮겨 갔습니다.',
    history: [30, 31, 33, 36, 34, 37, 39, 41, 40, 43, 44, 46, 47, 48, 50, 51, 52, 52],
    spread: [
      { country: 'US', since: '08.08', growth: 52.3, mentions: 318000 },
      { country: 'IN', since: '08.13', growth: 48.9, mentions: 174000 },
      { country: 'KR', since: '08.19', growth: 41.2, mentions: 152000 },
      { country: 'FR', since: '08.26', growth: 34.1, mentions: 126000 },
    ],
  },
  {
    id: 'techwear',
    keyword: '테크웨어',
    domain: '패션',
    emoji: '🧤',
    since: '2025.08.11',
    growth: 41.5,
    mentions: 398600,
    contents: 12980,
    countries: 39,
    summary: '도쿄 스트리트에서 자리를 잡고 서울과 베를린으로 넘어가는 중입니다.',
    history: [14, 16, 18, 19, 21, 23, 25, 26, 28, 30, 32, 33, 35, 36, 38, 39, 40, 42],
    spread: [
      { country: 'JP', since: '08.11', growth: 41.5, mentions: 148000 },
      { country: 'KR', since: '08.16', growth: 35.7, mentions: 124000 },
      { country: 'DE', since: '08.22', growth: 27.2, mentions: 86000 },
      { country: 'US', since: '08.29', growth: 21.4, mentions: 74000 },
    ],
  },
  {
    id: 'serverless-cost',
    keyword: '서버리스 비용',
    domain: '개발',
    emoji: '☁️',
    since: '2025.08.05',
    growth: -12.1,
    mentions: 287400,
    contents: 9870,
    countries: 31,
    summary: '요금제가 바뀐 뒤 미국과 영국에서 말수가 함께 줄었습니다.',
    history: [34, 33, 33, 31, 30, 29, 29, 28, 27, 26, 26, 25, 24, 23, 23, 22, 21, 21],
    spread: [
      { country: 'US', since: '08.05', growth: -12.1, mentions: 96000 },
      { country: 'GB', since: '08.09', growth: -9.8, mentions: 74000 },
      { country: 'DE', since: '08.18', growth: -4.2, mentions: 68000 },
    ],
  },
  {
    id: 'y2k-revival',
    keyword: 'Y2K 리바이벌',
    domain: '패션',
    emoji: '👖',
    since: '2025.08.18',
    growth: 33.9,
    mentions: 342900,
    contents: 11240,
    countries: 28,
    summary: '서울에서 시작해 방콕과 자카르타의 스트리트 이야기로 옮겨 갔습니다.',
    history: [12, 14, 16, 17, 19, 21, 22, 24, 25, 27, 28, 29, 30, 31, 32, 33, 33, 34],
    spread: [
      { country: 'KR', since: '08.18', growth: 33.9, mentions: 142000 },
      { country: 'TH', since: '08.24', growth: 28.4, mentions: 108000 },
      { country: 'ID', since: '08.30', growth: 22.6, mentions: 92000 },
    ],
  },
];

/** 왼쪽 목록의 거르개. 분야가 둘뿐이라 '전체' 없이 둘 중 하나를 늘 고른 채로 둡니다. */
export const DOMAIN_FILTERS = [...new Set(GLOBAL_TRENDS.map((trend) => trend.domain))];

export function countryOf(code: string): Country {
  return COUNTRIES[code];
}
