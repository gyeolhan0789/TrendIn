import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { FilterSelect } from '../../components/common/FilterSelect';
import { countryTrendLabel } from '../../features/globalTrend/conceptGloss';
import { CountryFlag } from '../../features/globalTrend/components/CountryFlag';
import { WorldMap } from '../../features/globalTrend/components/WorldMap';
import type { MapMode, MapStop } from '../../features/globalTrend/components/WorldMap';
import { countryGeoOf } from '../../features/globalTrend/data/countryGeo';
import { useCountryTrends } from '../../features/globalTrend/hooks/useCountryTrends';
import { useRegionCountries } from '../../features/globalTrend/hooks/useRegionCountries';
import { PICK_ZOOM, useSpreadTour } from '../../features/globalTrend/hooks/useSpreadTour';
import { useTrendRegionJourney } from '../../features/globalTrend/hooks/useTrendRegionJourney';
import { useTrendRegions } from '../../features/globalTrend/hooks/useTrendRegions';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { useTrends } from '../../features/trend/hooks/useTrends';
import { formatCount, formatGrowth } from '../../features/trend/trendFormat';
import { DEFAULT_REGION_PERIOD, REGION_PERIODS } from '../../constants/filterCodes';
import type { RegionPeriodCode } from '../../constants/filterCodes';
import type { CountryTrend, TrendJourneyStop, TrendRegion } from '../../features/globalTrend/types/globalTrend';
import type { Trend } from '../../features/trend/types/trend';

/*
 * 국가별 트렌드. 같은 표를 두 방향에서 읽는 화면입니다.
 *
 * '국가별 트렌드'는 나라를 먼저 고르고 그 나라의 TOP 트렌드를 봅니다. '트렌드별 추이'는
 * 트렌드를 먼저 고르고 그 말이 어느 나라에서 얼마나 불렸는지를 봅니다. 어느 쪽이든 지도는
 * 언급량만큼 나라를 진하게 칠해, 어디가 뜨거운지를 숫자보다 먼저 보여 줍니다.
 *
 * 30일은 한 가지를 더 합니다. 신규 트렌드에 한해 확산 경로를 따라가는 '흐름보기'가 열립니다.
 * 신규가 아닌 트렌드는 30일 안에 처음 잡힌 날이 대부분 첫날에 몰려, 따라갈 길이 나오지 않습니다.
 *
 * 화면은 한 화면 안에서 끝납니다. 지도는 창 크기에 맞춰 늘어나고, 스크롤은 왼쪽 목록과
 * 오른쪽 요약 안에서만 생깁니다. 지도를 보다가 아래로 밀려나면 흐름이 끊기기 때문입니다.
 */

/** 왼쪽 목록에 세울 트렌드 수. 칸이 좁아 더 받아도 스크롤만 길어집니다. */
const LIST_SIZE = 20;

/** 나라 하나에서 받아 올 트렌드 수. 시안은 다섯 줄이지만 넘겨 볼 여지를 조금 둡니다. */
const COUNTRY_TREND_SIZE = 10;

/** 안내가 떴다 사라지기까지. 한 줄을 읽고도 남되, 남아서 자리를 차지하지는 않을 만큼입니다. */
const TIP_MS = 4500;

/*
 * 목록에 덧붙일 신규 트렌드 수. 흐름보기가 열리는 것이 이쪽뿐이라 넉넉히 받습니다. 신규는
 * 언급량이 적어 두 목록을 한 줄로 세우면 대체로 아래쪽에 모이므로, 위쪽 자리를 빼앗지 않습니다.
 */
const NEW_SIZE = 20;

type Tab = 'country' | 'trend';

const PERIOD_LABELS: Record<RegionPeriodCode, string> = {
  '24H': '최근 24시간',
  '7D': '최근 7일',
  '30D': '최근 30일',
};

/** 기간 단추는 칸이 좁아 짧게 적습니다. 무엇을 기준으로 센 값인지는 지도 위 제목줄이 말합니다. */
const PERIOD_CHIPS: Record<RegionPeriodCode, string> = {
  '24H': '24시간',
  '7D': '7일',
  '30D': '30일',
};

function growthTone(growthRate: number | null) {
  if (growthRate === null) return '';
  if (growthRate >= 100) return 'is-hot';
  if (growthRate > 0) return 'is-up';
  return 'is-down';
}

/** 앞의 MM-DD 만 떼어 씁니다. Date 로 읽으면 시간대에 따라 하루가 밀릴 수 있습니다. */
function formatDay(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[2]}.${match[3]}` : value;
}

function GlobeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
    </svg>
  );
}

function WorldIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20" />
    </svg>
  );
}

function ZoomIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.35-4.35M11 8v6M8 11h6" />
    </svg>
  );
}

function FlowIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}

type Panel = 'left' | 'right';

const PANEL_LABELS: Record<Panel, string> = {
  left: '목록 패널',
  right: '요약 패널',
};

/*
 * 칸이 제 자리를 잃고 지도 위로 겹쳐 서는 폭입니다. global.css 의 같은 값과 짝입니다.
 * 요약이 먼저 물러나고, 더 좁아지면 목록도 따라갑니다.
 *
 * 겹쳐 서는 칸은 접힌 채로 시작해야 합니다. 펴진 채로 열리면 지도가 보이기도 전에 덮입니다.
 * 이 판단은 CSS 로 할 수 없습니다 — 접힘은 사용자가 손대는 상태라 화면이 들고 있습니다.
 */
const OVERLAY_AT: Record<Panel, string> = {
  right: '(max-width: 1180px)',
  left: '(max-width: 860px)',
};

function readOverlay(): Record<Panel, boolean> {
  /* 테스트처럼 matchMedia 가 없는 데서는 넓은 화면으로 봅니다 — 원래 모양 그대로입니다. */
  if (typeof window === 'undefined' || !window.matchMedia) return { left: false, right: false };
  return {
    left: window.matchMedia(OVERLAY_AT.left).matches,
    right: window.matchMedia(OVERLAY_AT.right).matches,
  };
}

/*
 * 지도 가장자리에 붙는 접기 손잡이입니다. 접힌 칸 자리에 두면 접는 순간 손잡이까지 사라져
 * 되돌릴 길이 없어지므로, 접히지 않는 지도 쪽에 붙여 둡니다.
 */
function FoldTab({ side, folded, onToggle }: { side: Panel; folded: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={`worldtrend-fold worldtrend-fold--${side} ${folded ? 'is-folded' : ''}`}
      onClick={onToggle}
      aria-expanded={!folded}
      title={`${PANEL_LABELS[side]} ${folded ? '펼치기' : '접기'}`}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M15 6l-6 6 6 6" />
      </svg>
      <span className="sr-only">{PANEL_LABELS[side]} {folded ? '펼치기' : '접기'}</span>
    </button>
  );
}

/** 순위 한 줄. 나라 순위와 트렌드 순위가 같은 모양이라 한곳에 둡니다. */
function RankRow({ rank, icon, name, value, share, onPick, selected = false }: {
  rank: number;
  /** 나라면 국기 그림, 트렌드면 표 하나. 자리를 늘 채워야 이름 시작점이 줄마다 맞습니다. */
  icon: ReactNode;
  name: string;
  value: string;
  share: number;
  /** 있으면 줄을 누를 수 있습니다. 지도에 자리가 없는 나라처럼 갈 곳이 없으면 비워 둡니다. */
  onPick?: () => void;
  selected?: boolean;
}) {
  const body = (
    <>
      <div className="worldtrend-rank-row">
        <span className={`worldtrend-rank-no ${rank <= 3 ? 'is-top' : ''}`}>{rank}</span>
        {icon}
        <span className="worldtrend-rank-name">{name}</span>
        <span className="worldtrend-rank-growth">{value}</span>
      </div>
      <div className="worldtrend-rank-bar">
        <span style={{ width: `${share}%` }} />
      </div>
    </>
  );

  return (
    <li>
      {onPick ? (
        <button
          type="button"
          className={`worldtrend-rank-pick ${selected ? 'is-selected' : ''}`}
          aria-pressed={selected}
          aria-label={`${name} ${value}, 지도에서 보기`}
          onClick={onPick}
        >
          {body}
        </button>
      ) : body}
    </li>
  );
}

interface CountrySummaryProps {
  country: TrendRegion;
  trends: CountryTrend[];
  loading: boolean;
  /** 이 분야의 나라를 가리지 않은 전체 언급량. 이 나라가 차지하는 몫을 내는 분모입니다. */
  worldMentionCount: number;
}

/**
 * 나라를 고른 뒤 읽는 칸. 국가별 화면에서는 이 칸이 주인공입니다.
 *
 * 이 화면이 답할 것은 '일본에서 무엇이 뜨고 있는가'이고, 지도는 '그 일본이 어디인가'까지만
 * 답합니다. 그래서 지도보다 이쪽에 힘을 주고 칸도 넓게 씁니다. 트렌드별 화면은 반대로 지도가
 * 주인공이라 그쪽 칸은 좁은 채로 둡니다. 두 화면의 무게가 다른 것이 오히려 맞습니다.
 *
 * 나라가 바뀌면 통째로 새로 그려지며 스며들 듯 바뀝니다(key). 글자만 조용히 갈리면 왼쪽을
 * 누른 사람이 오른쪽에서 무엇이 달라졌는지 모른 채 지나갑니다.
 */
function CountrySummary({ country, trends, loading, worldMentionCount }: CountrySummaryProps) {
  const share = worldMentionCount > 0
    ? Math.round((country.mentionCount / worldMentionCount) * 1000) / 10
    : null;
  const top = Math.max(...trends.map((item) => item.mentionCount), 1);

  return (
    <div className="worldtrend-focus" key={country.countryCode}>
      <header className="worldtrend-focus-head">
        <CountryFlag code={country.countryCode} className="worldtrend-focus-flag" />
        <h2>{country.countryName}</h2>
        <p className="worldtrend-focus-meta">
          <strong>{formatCount(country.mentionCount)}건</strong>
          <span>전체 {country.rank}위</span>
          {share !== null && <span>{share}%</span>}
        </p>
      </header>

      <section className="worldtrend-focus-body">
        {loading && <p className="worldtrend-summary-lead">불러오는 중…</p>}
        {!loading && trends.length === 0 && (
          <p className="worldtrend-summary-lead">이 기간에 이 나라에서 잡힌 언급이 없습니다.</p>
        )}
        <ol className="worldtrend-focus-list">
          {trends.map((item) => (
            <li key={item.keywordId}>
              {/* 두 자리로 맞춰 적습니다. 한 자리와 두 자리가 섞이면 이름 시작점이 줄마다 어긋납니다. */}
              <span className="worldtrend-focus-no">{String(item.rank).padStart(2, '0')}</span>
              <span className="worldtrend-focus-name">
                {countryTrendLabel(country.countryCode, item.keyword, item.conceptName)}
              </span>
              <span className="worldtrend-focus-value">{formatCount(item.mentionCount)}건</span>
              <span className="worldtrend-focus-bar">
                <span style={{ width: `${Math.round((item.mentionCount / top) * 100)}%` }} />
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

interface TrendSummaryProps {
  trend: Trend;
  period: RegionPeriodCode;
  regions: TrendRegion[];
  regionsLoading: boolean;
  journey: TrendJourneyStop[];
  journeyRange?: { startDate: string; endDate: string };
  /** 지도가 지금 비추는 나라. 목록에서 같은 줄을 도드라지게 합니다. */
  focusedCode?: string;
  /** 줄을 누르면 지도가 그 나라로 갑니다. 지도에 자리가 없는 나라면 `false` 를 돌려줍니다. */
  canPick: (code: string) => boolean;
  onPickCountry: (code: string) => void;
}

/**
 * 트렌드를 고른 채로 보는 오른쪽 칸. 어느 나라에서 얼마나 불렸는지에 답합니다.
 *
 * 시간에 따른 언급량 그래프는 두지 않습니다. 그 값은 나라를 도로 합친 전 세계 합계라, 나라별로
 * 갈라 보려고 들어온 이 화면에서 혼자 축이 다릅니다. 시간 흐름은 트렌드 상세가 답할 몫입니다.
 */
function TrendSummary({
  trend, period, regions, regionsLoading, journey, journeyRange, focusedCode, canPick, onPickCountry,
}: TrendSummaryProps) {
  const top = Math.max(...regions.map((region) => region.mentionCount), 1);
  const firstStop = journey[0];

  return (
    <>
      <section className="worldtrend-card">
        <div className="worldtrend-card-head">
          <h2>선택 트렌드</h2>
          <span className="worldtrend-card-note">{PERIOD_LABELS[period]}</span>
        </div>
        <h3 className="worldtrend-summary-title">{trend.keyword}</h3>
        {/*
          * 줄글 설명은 두지 않습니다. 이 칸이 답할 것은 '어디서 얼마나'이고, 그것은 아래 세
          * 숫자가 이미 말합니다. 설명이 있는 트렌드보다 없는 트렌드가 많아, 있을 때는 숫자와
          * 겹쳐 읽히고 없을 때는 빈 문구 한 줄이 자리만 차지했습니다.
          */}
        <dl className="worldtrend-facts">
          <div>
            <dt>언급된 나라</dt>
            <dd>{regionsLoading ? '…' : `${regions.length}개국`}</dd>
          </div>
          <div>
            <dt>전체 언급량</dt>
            <dd>{formatCount(trend.mentionCount)}건</dd>
          </div>
          {/* 확산 경로는 흐름보기에서만 받습니다. 받지 않은 것을 '—'로 두면 없는 것으로 읽힙니다. */}
          {firstStop && (
            <div>
              <dt>처음 잡힌 곳</dt>
              <dd>{firstStop.countryName} · {formatDay(firstStop.firstDetectedDate)}</dd>
            </div>
          )}
        </dl>
      </section>

      <section className="worldtrend-card">
        <div className="worldtrend-card-head">
          <h2>국가별 언급량</h2>
          <span className="worldtrend-card-note">{PERIOD_LABELS[period]}</span>
        </div>
        {regionsLoading && <p className="worldtrend-summary-lead">불러오는 중…</p>}
        {!regionsLoading && regions.length === 0 && (
          <p className="worldtrend-summary-lead">이 기간에 나라별로 잡힌 언급이 없습니다.</p>
        )}
        <ol className="worldtrend-rank">
          {/* 지도에 자리가 없는 나라도 언급량은 실제로 잡힌 값이라 목록에서는 빼지 않습니다. */}
          {regions.map((region) => (
            <RankRow
              key={region.countryCode}
              rank={region.rank}
              icon={<CountryFlag code={region.countryCode} className="worldtrend-rank-flag" />}
              name={region.countryName}
              value={`${formatCount(region.mentionCount)}건`}
              share={Math.round((region.mentionCount / top) * 100)}
              /* 지도의 핀을 누른 것과 같습니다. 목록과 지도가 따로 놀면 안 됩니다. */
              onPick={canPick(region.countryCode) ? () => onPickCountry(region.countryCode) : undefined}
              selected={region.countryCode === focusedCode}
            />
          ))}
        </ol>
      </section>

      {/*
        * 두 목록이 같은 30일을 보는데도 차례가 다릅니다. 하나는 처음 잡힌 날, 다른 하나는
        * 언급량이라서입니다. 밝히지 않으면 아래 경로와 위 순위가 어긋난 것을 오류로 읽습니다.
        */}
      {journeyRange && journey.length > 0 && (
        <p className="worldtrend-note">
          확산 경로는 나라마다 처음 잡힌 날 차례({formatDay(journeyRange.startDate)}–{formatDay(journeyRange.endDate)})이고,
          위 순위는 같은 30일 동안의 언급량 차례입니다. 그래서 두 목록의 차례가 다릅니다.
        </p>
      )}
    </>
  );
}

export function GlobalTrendsPage() {
  const [tab, setTab] = useState<Tab>('country');
  const [domain, setDomain] = useState<string>();
  const [period, setPeriod] = useState<RegionPeriodCode>(DEFAULT_REGION_PERIOD);
  const [selectedCountryCode, setSelectedCountryCode] = useState<string>();
  const [selectedTrendId, setSelectedTrendId] = useState<number>();
  /* 흐름보기를 눌러 두었는지. 조건이 맞지 않는 기간·트렌드에서는 눌러 두어도 켜지지 않습니다. */
  const [flowWanted, setFlowWanted] = useState(false);
  /* 트렌드별 탭을 연 순간 잠깐 띄우는 안내. 스스로 사라집니다. */
  const [flowTip, setFlowTip] = useState(false);
  /*
   * 말풍선 꼬리가 가리킬 자리. 기간 단추는 글자폭만큼만 넓어 '24시간'과 '30일'의 폭이 다르고,
   * 글꼴이나 글자가 바뀌면 그 폭도 달라집니다. 어림한 값을 박아 두면 그때마다 꼬리가 엉뚱한
   * 단추를 가리키므로, 띄우는 순간 30일 단추의 한가운데를 재서 씁니다.
   */
  const chipsRef = useRef<HTMLDivElement>(null);
  const [tipX, setTipX] = useState(0);
  const [mode, setMode] = useState<MapMode>('globe');
  /* 지도를 넓게 보고 싶을 때 양옆 칸을 접어 둘 수 있습니다. 좁은 화면에서는 접힌 채로 엽니다. */
  const [folded, setFolded] = useState<Record<Panel, boolean>>(readOverlay);
  /* 목록이 지도를 덮고 있는지. 덮고 있을 때만, 고르고 나서 칸을 닫아 줍니다. */
  const [listOverlaid, setListOverlaid] = useState(() => readOverlay().left);

  const isCountryTab = tab === 'country';
  /*
   * 국가별 화면은 늘 평면 지도입니다. 여기서 지도가 할 일은 '고른 나라가 세계 어디쯤이고 다른
   * 나라와 견주어 얼마나 진한가'까지인데, 지구본은 절반이 뒤로 돌아가 있어 그 견줌이 한눈에
   * 들어오지 않습니다. 트렌드별 화면은 반대로 확산 경로가 주인공이라 지구본이 제 몫을 합니다.
   * 고른 차원은 그대로 두어, 트렌드별로 돌아가면 보던 대로 이어집니다.
   */
  const mapMode: MapMode = isCountryTab ? 'flat' : mode;

  /*
   * 고를 수 있는 분야 전체가 아니라 내가 고른 분야만 받습니다. 트렌드 탐색과 같은 이유로,
   * 고르지 않은 분야까지 칸으로 내밀면 거르개가 아니라 남의 목록이 됩니다.
   */
  const domainsQuery = useMyDomains(true);
  const domains = useMemo(() => domainsQuery.data ?? [], [domainsQuery.data]);
  // 받아 왔는데 비어 있으면 아직 아무 분야도 고르지 않은 것입니다. 받는 중인 것과 갈라야 합니다.
  const noChosenDomain = domainsQuery.isSuccess && domains.length === 0;
  // 분야를 고쳐 골라 눌러 둔 분야가 목록에서 빠지면, 없는 분야로 조회하지 않게 첫 분야로 돌아갑니다.
  const activeDomain = domains.some((option) => option.domain === domain) ? domain : domains[0]?.domain;

  /* 나라 목록은 지도를 칠하는 값이기도 해서 국가별 탭에서만 부릅니다. */
  const countriesQuery = useRegionCountries(isCountryTab ? activeDomain : undefined, period);
  const countries = useMemo(() => countriesQuery.data?.countries ?? [], [countriesQuery.data]);
  // 기간이나 분야를 바꿔 고른 나라가 목록에서 사라지면 첫 나라로 옮겨 갑니다.
  const country = countries.find((item) => item.countryCode === selectedCountryCode) ?? countries[0];
  const countryTrendsQuery = useCountryTrends(
    activeDomain, isCountryTab ? country?.countryCode : undefined, period, COUNTRY_TREND_SIZE,
  );
  const countryTrends = useMemo(() => countryTrendsQuery.data?.trends ?? [], [countryTrendsQuery.data]);

  const currentQuery = useTrends(!isCountryTab && activeDomain
    ? { domain: activeDomain, type: 'CURRENT', period, page: 0, size: LIST_SIZE }
    : undefined);
  /*
   * 신규 트렌드는 언급량이 적어 현재 목록 스무 줄 안에 거의 들지 않습니다. 따로 받아 붙이지
   * 않으면 흐름보기가 열리는 트렌드에 이 화면에서 닿을 길이 아예 없습니다.
   */
  const newQuery = useTrends(!isCountryTab && activeDomain
    ? { domain: activeDomain, type: 'NEW', period, page: 0, size: NEW_SIZE }
    : undefined);

  const trends = useMemo(() => {
    const merged = [...(currentQuery.data?.trends ?? [])];
    const seen = new Set(merged.map((item) => item.trendId));
    for (const item of newQuery.data?.trends ?? []) {
      if (seen.has(item.trendId)) continue;
      seen.add(item.trendId);
      merged.push(item);
    }
    /* 두 목록을 이어 붙인 자리에서 언급량이 다시 커집니다. 한 줄로 세워야 위에서부터 읽힙니다. */
    return merged.sort((left, right) => right.mentionCount - left.mentionCount);
  }, [currentQuery.data, newQuery.data]);
  const trend = trends.find((item) => item.trendId === selectedTrendId) ?? trends[0];
  const trendId = trend?.trendId;

  const regionsQuery = useTrendRegions(isCountryTab ? undefined : trendId, period);
  const regions = useMemo(() => regionsQuery.data?.regions ?? [], [regionsQuery.data]);

  /*
   * 흐름보기가 열리는 조건입니다. 확산 경로는 트렌드 하나의 이야기라 국가별 탭에는 따라갈
   * 대상이 없고, 30일이 아니면 경로를 낼 만큼 날짜가 쌓이지 않으며, 신규가 아닌 트렌드는
   * 처음 잡힌 날이 구간 첫날에 몰려 길이 한 점으로 뭉갭니다.
   */
  const isNewTrend = trend?.trendTypes.includes('NEW') ?? false;
  const canFlow = !isCountryTab && period === '30D' && isNewTrend;
  const flowing = canFlow && flowWanted;

  const journeyQuery = useTrendRegionJourney(canFlow ? trendId : undefined);
  const journey = useMemo(() => journeyQuery.data?.regions ?? [], [journeyQuery.data]);

  /*
   * 지도에 올릴 나라입니다. 흐름보기는 퍼져 나간 차례여야 하므로 확산 경로에서 만들고,
   * 나머지는 언급량 차례 그대로 올립니다. 지도가 자리를 모르는 나라는 핀을 찍을 수 없어 빠집니다.
   */
  const stops = useMemo<MapStop[]>(() => {
    if (flowing) {
      const mentionByCode = new Map(regions.map((region) => [region.countryCode, region.mentionCount]));
      return journey.flatMap((stop) => {
        const geo = countryGeoOf(stop.countryCode);
        if (!geo) return [];
        const mentionCount = mentionByCode.get(stop.countryCode) ?? 0;
        return [{
          country: geo,
          weight: mentionCount,
          label: mentionCount > 0 ? `${formatCount(mentionCount)}건` : '최근 잠잠',
          since: formatDay(stop.firstDetectedDate),
        }];
      });
    }
    const rows = isCountryTab ? countries : regions;
    return rows.flatMap((row) => {
      const geo = countryGeoOf(row.countryCode);
      if (!geo) return [];
      return [{ country: geo, weight: row.mentionCount, label: `${formatCount(row.mentionCount)}건` }];
    });
  }, [flowing, isCountryTab, countries, regions, journey]);

  const route = useMemo(() => stops.map((stop) => stop.country), [stops]);
  /* 따라가기는 흐름보기에서만 저절로 시작합니다. 나머지 화면에서는 지도가 가만히 있어야 읽힙니다. */
  /* 평면 지도에서는 세계를 통째로 둔 채 비행기만 건넙니다. 지구본은 뒤쪽이 가려져 따라 돕니다. */
  const tour = useSpreadTour(route, flowing ? `flow-${trendId}` : null, mapMode === 'globe');
  const { goTo, showWorld } = tour;

  // 고른 것이 밀려났으면 지금 보고 있는 것으로 상태를 맞춰 둡니다.
  useEffect(() => {
    if (trendId !== undefined && trendId !== selectedTrendId) setSelectedTrendId(trendId);
  }, [trendId, selectedTrendId]);
  useEffect(() => {
    const code = country?.countryCode;
    if (code !== undefined && code !== selectedCountryCode) setSelectedCountryCode(code);
  }, [country?.countryCode, selectedCountryCode]);

  /*
   * 탭을 바꾸면 지도를 세계 전체로 되돌립니다. 두 탭 모두 먼저 답해야 할 것이 '어느 나라가
   * 뜨거운가'이고, 앞 탭에서 들여다보던 배율이 남아 있으면 지도에 한 나라만 남습니다.
   */
  /*
   * 나라를 고르는 것과 지도를 들여다보는 것을 갈라 둡니다.
   *
   * 고르면 지도는 그 자리에 그대로 있고 그 나라만 도드라집니다. 눌렀다고 지도가 확 당겨지면
   * 세계 안에서 그 나라가 어디쯤인지, 다른 나라와 견주어 얼마나 뜨거운지가 함께 사라집니다.
   * 고른 뒤 정작 답이 바뀌는 곳은 오른쪽 칸인데 눈은 지도 움직임을 좇게 됩니다.
   *
   * 크게 보고 싶은 사람은 따로 있으므로, 그 일은 '선택 국가 확대' 단추로 옮겼습니다.
   */
  const pickCountry = useCallback((code: string | undefined) => {
    if (!code) return;
    setSelectedCountryCode(code);
  }, []);

  const zoomToCountry = useCallback(() => {
    const index = stops.findIndex((stop) => stop.country.code === country?.countryCode);
    if (index >= 0) goTo(index, PICK_ZOOM);
  }, [stops, country?.countryCode, goTo]);

  /*
   * 트렌드별 탭 오른쪽 목록에서 나라를 누르면 지도가 그 나라로 갑니다. 지도의 핀을 누른 것과
   * 같은 움직임입니다(`onPickStop`). 국가별 탭과 달리 이 화면은 지도가 주인공이라 다가가도 됩니다.
   */
  const canPickStop = useCallback(
    (code: string) => stops.some((stop) => stop.country.code === code),
    [stops],
  );
  const goToCountry = useCallback((code: string) => {
    const index = stops.findIndex((stop) => stop.country.code === code);
    if (index >= 0) goTo(index);
  }, [stops, goTo]);

  const switchTab = useCallback((next: Tab) => {
    setTab(next);
    setFlowWanted(false);
    setFlowTip(next === 'trend');
    showWorld();
  }, [showWorld]);

  /* 띄운 안내는 스스로 걷힙니다. 탭을 오가며 여러 번 열어도 타이머가 겹치지 않게 치워 둡니다. */
  useEffect(() => {
    if (!flowTip) return;
    const timer = window.setTimeout(() => setFlowTip(false), TIP_MS);
    return () => window.clearTimeout(timer);
  }, [flowTip]);

  useEffect(() => {
    if (!flowTip) return;
    /* 칸이 position: relative 라 offsetLeft 가 곧 그 칸 안에서의 자리입니다. */
    const chip = chipsRef.current?.querySelector<HTMLElement>('[data-period="30D"]');
    if (chip) setTipX(chip.offsetLeft + chip.offsetWidth / 2);
  }, [flowTip]);

  const stopFlow = useCallback(() => {
    setFlowWanted(false);
    showWorld();
  }, [showWorld]);

  const toggleFold = (panel: Panel) => setFolded((current) => ({ ...current, [panel]: !current[panel] }));

  /*
   * 폭을 오갈 때 접힘을 그 폭의 기본값으로 되돌립니다. 손대 둔 값을 들고 넘어가면, 좁아지는
   * 순간 칸이 지도를 덮은 채 나타나거나 넓어졌는데 빈 자리만 남습니다. 창 크기를 바꾸는 일은
   * 드물고, 그때 기대하는 것은 '그 폭에 맞는 모양'이지 직전에 눌러 둔 상태가 아닙니다.
   */
  useEffect(() => {
    if (!window.matchMedia) return;
    const stops = (Object.keys(OVERLAY_AT) as Panel[]).map((panel) => {
      const media = window.matchMedia(OVERLAY_AT[panel]);
      const apply = (event: MediaQueryListEvent) => {
        setFolded((current) => ({ ...current, [panel]: event.matches }));
        if (panel === 'left') setListOverlaid(event.matches);
      };
      media.addEventListener('change', apply);
      return () => media.removeEventListener('change', apply);
    });
    return () => stops.forEach((stop) => stop());
  }, []);

  /*
   * 겹쳐 뜬 목록에서 골랐을 때의 뒷정리입니다. 목록을 닫고 요약을 엽니다.
   *
   * 닫는 이유: 고른 결과는 지도와 요약에 나타나는데 목록이 그 위를 덮고 있어, 그대로 두면
   * 눌러도 아무 일도 없는 것처럼 보입니다.
   *
   * 여는 이유: 여기서 고르는 것은 읽기 위해서입니다. 닫기만 하면 지도에 색만 바뀐 채 남고,
   * 정작 답인 요약은 반대쪽 모서리 손잡이를 찾아내야 나옵니다. 넓은 화면에서는 하지 않습니다 —
   * 거기서 접힌 요약은 사용자가 지도를 넓게 보려고 직접 접어 둔 것입니다.
   */
  const afterPickOnOverlay = useCallback(() => {
    if (listOverlaid) setFolded({ left: true, right: false });
  }, [listOverlaid]);

  const listLoading = domainsQuery.isLoading
    || (isCountryTab ? countriesQuery.isLoading : currentQuery.isLoading);
  const listFailed = domainsQuery.isError
    || (isCountryTab ? countriesQuery.isError : currentQuery.isError || newQuery.isError);
  const listEmpty = !listLoading && !listFailed && !noChosenDomain
    && (isCountryTab ? countries.length === 0 : trends.length === 0);
  const retry = () => {
    if (domainsQuery.isError) void domainsQuery.refetch();
    else if (isCountryTab) void countriesQuery.refetch();
    else {
      if (currentQuery.isError) void currentQuery.refetch();
      if (newQuery.isError) void newQuery.refetch();
    }
  };

  return (
    <div className={`worldtrend-page${isCountryTab ? ' is-country' : ''}${mapMode === 'globe' ? ' is-globe' : ''}${folded.left ? ' is-left-folded' : ''}${folded.right ? ' is-right-folded' : ''}`}>
      <aside className="worldtrend-list">
        {/* 두 탭은 같은 자료를 반대로 읽습니다. 보기 방식이지 다른 화면이 아니라 한 칸 안에 둡니다. */}
        <div className="worldtrend-tabs" role="tablist" aria-label="보기 방식">
          <button
            type="button"
            role="tab"
            aria-selected={isCountryTab}
            className={isCountryTab ? 'is-selected' : ''}
            onClick={() => switchTab('country')}
          >
            국가별 트렌드
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={!isCountryTab}
            className={!isCountryTab ? 'is-selected' : ''}
            onClick={() => switchTab('trend')}
          >
            트렌드별 추이
          </button>
        </div>

        {/*
          * 분야는 대시보드·키워드 화면이 쓰는 드롭다운 한 칸을 그대로 씁니다. 칸이 좁아 조각으로
          * 늘어놓으면 분야가 늘어날수록 여러 줄로 접히고, 그만큼 목록이 아래로 밀립니다.
          */}
        <div className="worldtrend-filter">
          <FilterSelect
            label="카테고리"
            value={activeDomain ?? ''}
            options={domains.map((option) => ({ value: option.domain, label: option.name }))}
            onChange={setDomain}
            disabled={domains.length === 0}
          />
        </div>

        {/* 나라별 자료는 하루 단위라 세 기간을 모두 셀 수 있습니다. */}
        <div className="worldtrend-chips" ref={chipsRef}>
          {/*
            * 30일에서 무엇을 더 볼 수 있는지, 그 단추 바로 위에서 한 번 알려 주고 사라집니다.
            * 오른쪽 칸 아래에 늘 띄워 두었더니 조건이 맞을 때도 문구가 남아 있어, 무엇이 잘못된
            * 줄 알고 읽게 됐습니다. 손이 기간을 고르려는 그 자리에서 한 번이면 충분합니다.
            *
            * 눌러야 할 것이 아니므로 손을 받지 않습니다. 아래 카테고리 칸을 잠깐 가리는데,
            * 손을 받으면 그 칸을 누르려던 사람이 허공을 누르게 됩니다.
            */}
          {flowTip && (
            <p className="worldtrend-tip" role="status" style={{ '--tip-x': `${tipX}px` } as CSSProperties}>
              <strong>30일 보기</strong>에서는 신규 트렌드의 전 세계 흐름을 눈으로 확인할 수 있습니다.
            </p>
          )}
          {REGION_PERIODS.map((code) => (
            <button
              type="button"
              key={code}
              className={`worldtrend-chip ${code === period ? 'is-selected' : ''}`}
              data-period={code}
              aria-pressed={code === period}
              onClick={() => setPeriod(code)}
            >
              {PERIOD_CHIPS[code]}
            </button>
          ))}
        </div>

        <p className="worldtrend-list-hint">
          {isCountryTab
            ? '나라를 고르면 그 나라에서 많이 불린 트렌드를 봅니다.'
            : '트렌드를 고르면 그 말이 어느 나라에서 얼마나 불렸는지를 봅니다.'}
        </p>

        {listLoading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}
        {!listLoading && listFailed && (
          <div className="trendin-state is-error" role="alert">
            <p>{isCountryTab ? '나라별 언급량을' : '트렌드를'} 불러오지 못했습니다.</p>
            <button type="button" onClick={retry}>다시 시도</button>
          </div>
        )}
        {/*
          * 고른 분야가 없으면 지도에 올릴 것도 없습니다. '집계된 자료가 없다'고 하면 서버 탓처럼
          * 읽히므로, 무엇이 비었고 어디서 채우는지를 짚어 줍니다.
          */}
        {noChosenDomain && (
          <div className="trendin-state" role="status">
            <p>아직 고른 관심 분야가 없습니다.</p>
            <Link to="/mypage/profile">관심 분야 고르러 가기</Link>
          </div>
        )}
        {listEmpty && (
          <div className="trendin-state" role="status"><p>이 구간에 집계된 자료가 없습니다.</p></div>
        )}

        <ul className="worldtrend-items">
          {isCountryTab && countries.map((item) => (
            <li key={item.countryCode}>
              <button
                type="button"
                className={`worldtrend-item ${item.countryCode === country?.countryCode ? 'is-selected' : ''}`}
                onClick={() => { pickCountry(item.countryCode); afterPickOnOverlay(); }}
              >
                <span className="worldtrend-item-emoji">
                  <CountryFlag code={item.countryCode} className="worldtrend-item-flag" />
                </span>
                {/*
                  * 언급량은 적지 않습니다. 고른 나라의 언급량·순위·몫은 오른쪽 칸이 크게 말하고
                  * 있어, 여기 또 두면 같은 숫자를 두 번 읽게 됩니다. 이 목록은 고르는 도구입니다.
                  */}
                <span className="worldtrend-item-body">
                  <span className="worldtrend-item-name">{item.countryName}</span>
                </span>
                <span className="worldtrend-item-rank">{item.rank}위</span>
              </button>
            </li>
          ))}
          {!isCountryTab && trends.map((item, index) => (
            <li key={item.trendId}>
              <button
                type="button"
                className={`worldtrend-item ${item.trendId === trendId ? 'is-selected' : ''}`}
                onClick={() => { setSelectedTrendId(item.trendId); afterPickOnOverlay(); }}
              >
                {/*
                  * 시안의 이모지 자리입니다. 서버가 주지 않는 그림 대신 자리를 세웁니다. 서버가 준
                  * 순위(rank)는 갈래 안에서의 순위라, 현재와 신규를 한 줄로 세운 여기서는 같은
                  * 숫자가 두 번 나옵니다. 이 목록에서의 자리를 그대로 쓰는 편이 맞습니다.
                  */}
                <span className="worldtrend-item-emoji" aria-hidden="true">{index + 1}</span>
                <span className="worldtrend-item-body">
                  <span className="worldtrend-item-name">
                    {item.keyword}
                    {/* 흐름보기가 열리는 트렌드를 목록에서 바로 가릴 수 있게 표를 답니다. */}
                    {item.trendTypes.includes('NEW') && <span className="worldtrend-item-new">NEW</span>}
                  </span>
                  <span className="worldtrend-item-meta">
                    <span className="worldtrend-item-domain">{item.domain.name}</span>
                    <span>{formatCount(item.mentionCount)}건</span>
                  </span>
                  <span className="worldtrend-item-trail">
                    <span className={`worldtrend-item-growth ${growthTone(item.growthRate)}`}>
                      {formatGrowth(item.growthRate)}
                    </span>
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="worldtrend-stage">
        {mapMode === 'globe' && (
          <div className="worldtrend-star-bg" aria-hidden="true" />
        )}
        <div className="worldtrend-map">
          <WorldMap
            mode={mapMode}
            view={tour.view}
            stops={stops}
            trail={flowing}
            selectedCode={isCountryTab ? country?.countryCode : null}
            focusIndex={tour.focusIndex}
            stopIndex={tour.stopIndex}
            legProgress={tour.legProgress}
            onPickStop={(index) => {
              /*
               * 국가별 탭에서는 지도를 눌러도 나라를 고른 것입니다. 목록과 지도가 따로 놀면 안 됩니다.
               * 지도를 그 나라로 끌어당기지는 않습니다. 이 화면이 먼저 답할 것은 전체 지도에서
               * 어디가 진한가이고, 한 나라로 다가가면 그 답이 화면 밖으로 나갑니다.
               */
              if (isCountryTab) pickCountry(stops[index]?.country.code);
              else goTo(index);
            }}
            onSteer={tour.steer}
          />

          <div className="worldtrend-toolbar">
            <div className="worldtrend-controls">
              {/* 흐름보기는 조건이 맞을 때만 내놓습니다. 눌러도 안 되는 단추를 두면 조건을 되물어야 합니다. */}
              {canFlow && (
                <div className="worldtrend-toggle" role="group" aria-label="지도 보기 방식">
                  <button type="button" className={flowing ? '' : 'is-selected'} aria-pressed={!flowing} onClick={stopFlow}>
                    <WorldIcon />
                    전체보기
                  </button>
                  <button
                    type="button"
                    className={flowing ? 'is-selected' : ''}
                    aria-pressed={flowing}
                    /* 들여다보던 배율에서 시작하면 길의 첫 구간이 화면 밖에 있습니다. */
                    onClick={() => { showWorld(); setFlowWanted(true); }}
                  >
                    <FlowIcon />
                    흐름보기
                  </button>
                </div>
              )}

              {/* 평면이 2D, 지구본이 3D 입니다. 무엇이 켜져 있는지 한 칸 안에서 갈립니다. */}
              {!isCountryTab && (
              <div className="worldtrend-toggle" role="group" aria-label="지도 차원">
                <button
                  type="button"
                  className={mode === 'flat' ? 'is-selected' : ''}
                  aria-pressed={mode === 'flat'}
                  title="평면 지도"
                  onClick={() => setMode('flat')}
                >
                  <GridIcon />
                  2D
                </button>
                <button
                  type="button"
                  className={mode === 'globe' ? 'is-selected' : ''}
                  aria-pressed={mode === 'globe'}
                  title="지구본"
                  onClick={() => setMode('globe')}
                >
                  <GlobeIcon />
                  3D
                </button>
              </div>
              )}

              {/* 고르는 것과 들여다보는 것을 가른 뒤, 들여다보는 쪽을 맡는 단추입니다. */}
              {isCountryTab && country && (
                <div className="worldtrend-tourbtns">
                  <button type="button" onClick={zoomToCountry}>
                    <ZoomIcon />
                    선택 국가 확대
                  </button>
                </div>
              )}

              {flowing && (
                <div className="worldtrend-tourbtns">
                  <button type="button" disabled={stops.length < 2} onClick={tour.playing ? tour.pause : tour.play}>
                    {tour.playing ? '멈춤' : '경로 따라가기'}
                  </button>
                </div>
              )}
            </div>
          </div>

          <FoldTab side="left" folded={folded.left} onToggle={() => toggleFold('left')} />
          <FoldTab side="right" folded={folded.right} onToggle={() => toggleFold('right')} />
        </div>

        {/*
          * 확산 경로는 칸에 담지 않고 지도 아래쪽에 그대로 띄웁니다. 나라 수·언급량은 오른쪽
          * 요약에 이미 있어, 아래에 또 두면 같은 숫자를 두 번 읽게 됩니다.
          */}
        {flowing && (
          <div className="worldtrend-flow">
            <div className="worldtrend-flow-inner">
              {journeyQuery.isLoading && <p className="worldtrend-flow-note">확산 경로를 불러오는 중…</p>}
              {journeyQuery.isSuccess && journey.length === 0 && (
                <p className="worldtrend-flow-note">아직 나라별로 잡힌 언급이 없습니다.</p>
              )}
              <ol className="worldtrend-flow-stops">
                {stops.map((stop, index) => (
                  <li key={stop.country.code}>
                    <button
                      type="button"
                      className={`worldtrend-flow-stop ${index <= tour.focusIndex ? 'is-passed' : ''} ${index === tour.stopIndex ? 'is-here' : ''}`}
                      onClick={() => goTo(index)}
                    >
                      <CountryFlag code={stop.country.code} className="worldtrend-flow-flag" />
                      <span className="worldtrend-flow-name">{stop.country.name}</span>
                      <span className="worldtrend-flow-date">{stop.since}</span>
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        )}
      </main>

      <aside className="worldtrend-side">
        {isCountryTab && country && (
          <CountrySummary
            country={country}
            trends={countryTrends}
            loading={countryTrendsQuery.isLoading}
            worldMentionCount={countriesQuery.data?.totalMentionCount ?? 0}
          />
        )}
        {!isCountryTab && trend && (
          <TrendSummary
            trend={trend}
            period={period}
            regions={regions}
            regionsLoading={regionsQuery.isLoading}
            journey={journey}
            journeyRange={journeyQuery.data}
            focusedCode={stops[tour.focusIndex]?.country.code}
            canPick={canPickStop}
            onPickCountry={goToCountry}
          />
        )}
        {((isCountryTab && !country) || (!isCountryTab && !trend)) && (
          <section className="worldtrend-card">
            <div className="worldtrend-card-head"><h2>요약</h2></div>
            <p className="worldtrend-summary-lead">
              왼쪽에서 {isCountryTab ? '나라를' : '트렌드를'} 고르면 여기에 자세한 값을 보여 드립니다.
            </p>
          </section>
        )}

      </aside>
    </div>
  );
}
