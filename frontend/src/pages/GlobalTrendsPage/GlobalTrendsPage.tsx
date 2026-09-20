import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { WorldMap } from '../../features/globalTrend/components/WorldMap';
import type { MapMode, MapStop } from '../../features/globalTrend/components/WorldMap';
import { countryGeoOf } from '../../features/globalTrend/data/countryGeo';
import { useSpreadTour } from '../../features/globalTrend/hooks/useSpreadTour';
import { useTrendRegionJourney } from '../../features/globalTrend/hooks/useTrendRegionJourney';
import { useTrendRegions } from '../../features/globalTrend/hooks/useTrendRegions';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { TrendSparkline } from '../../features/trend/components/TrendSparkline';
import { useTrendDetail } from '../../features/trend/hooks/useTrendDetail';
import { useTrendHistory } from '../../features/trend/hooks/useTrendHistory';
import { useTrends } from '../../features/trend/hooks/useTrends';
import { formatCount, formatGrowth } from '../../features/trend/trendFormat';
import { DEFAULT_REGION_PERIOD, REGION_PERIODS } from '../../constants/filterCodes';
import type { RegionPeriodCode } from '../../constants/filterCodes';
import type { TrendJourneyStop, TrendRegion } from '../../features/globalTrend/types/globalTrend';
import type { Trend } from '../../features/trend/types/trend';

/*
 * 국가별 트렌드. 키워드 하나를 고르면 그 말이 어느 나라에서 시작해 어디로 이어졌는지,
 * 지도가 그 나라를 차례로 확대하며 따라갑니다.
 *
 * 화면은 한 화면 안에서 끝납니다. 지도는 창 크기에 맞춰 늘어나고, 스크롤은 왼쪽 목록과
 * 오른쪽 요약 안에서만 생깁니다. 지도를 보다가 아래로 밀려나면 흐름이 끊기기 때문입니다.
 *
 * 나라 자료를 부르는 것은 고른 키워드 하나뿐입니다. 목록 항목마다 부르면 한 화면에 수십 번이 됩니다.
 */

/** 목록에 세울 트렌드 수. 왼쪽 칸이 좁아 더 받아도 스크롤만 길어집니다. */
const LIST_SIZE = 20;

const PERIOD_LABELS: Record<RegionPeriodCode, string> = {
  '24H': '최근 24시간',
  '7D': '최근 7일',
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

type Panel = 'left' | 'right';

const PANEL_LABELS: Record<Panel, string> = {
  left: '키워드 목록',
  right: '요약 패널',
};

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

interface SummaryPanelProps {
  trend: Trend;
  period: RegionPeriodCode;
  regions: TrendRegion[];
  regionsLoading: boolean;
  journey: TrendJourneyStop[];
  journeyRange?: { startDate: string; endDate: string };
}

function SummaryPanel({ trend, period, regions, regionsLoading, journey, journeyRange }: SummaryPanelProps) {
  const detailQuery = useTrendDetail(trend.trendId, period);
  const historyQuery = useTrendHistory(trend.trendId, period);

  const history = historyQuery.data?.history ?? [];
  const top = Math.max(...regions.map((region) => region.mentionCount), 1);
  const detail = detailQuery.data;
  const firstStop = journey[0];

  return (
    <>
      <section className="worldtrend-card">
        <div className="worldtrend-card-head">
          <h2>글로벌 요약</h2>
          <span className="worldtrend-card-note">{PERIOD_LABELS[period]}</span>
        </div>
        <h3 className="worldtrend-summary-title">{trend.keyword}</h3>
        {/* 서버가 지어 둔 설명이 있으면 그대로 씁니다. 없는 트렌드가 더 많습니다. */}
        <p className="worldtrend-summary-lead">
          {detail?.summary ?? trend.description ?? '아직 정리된 설명이 없습니다.'}
        </p>
        <dl className="worldtrend-facts">
          <div>
            <dt>언급된 나라</dt>
            <dd>{regionsLoading ? '…' : `${regions.length}개국`}</dd>
          </div>
          <div>
            <dt>전체 언급량</dt>
            <dd>{formatCount(trend.mentionCount)}건</dd>
          </div>
          <div>
            <dt>처음 잡힌 곳</dt>
            <dd>{firstStop ? `${firstStop.countryName} · ${formatDay(firstStop.firstDetectedDate)}` : '—'}</dd>
          </div>
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
          {regions.map((region) => {
            const country = countryGeoOf(region.countryCode);
            return (
              <li key={region.countryCode}>
                <div className="worldtrend-rank-row">
                  <span className={`worldtrend-rank-no ${region.rank <= 3 ? 'is-top' : ''}`}>{region.rank}</span>
                  <span className="worldtrend-rank-flag" aria-hidden="true">{country?.flag}</span>
                  {/* 지도에 자리가 없는 나라도 언급량은 실제로 잡힌 값이라 목록에서는 빼지 않습니다. */}
                  <span className="worldtrend-rank-name">{region.countryName}</span>
                  <span className="worldtrend-rank-growth">{formatCount(region.mentionCount)}</span>
                </div>
                <div className="worldtrend-rank-bar">
                  <span style={{ width: `${Math.round((region.mentionCount / top) * 100)}%` }} />
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="worldtrend-card worldtrend-card--chart">
        <div className="worldtrend-card-head">
          <h2>언급량 변화 추이</h2>
          <span className="worldtrend-card-note">{PERIOD_LABELS[period]}</span>
        </div>
        {history.length === 0
          ? <p className="worldtrend-summary-lead">{historyQuery.isLoading ? '불러오는 중…' : '표시할 추이가 없습니다.'}</p>
          : (
            <>
              <TrendSparkline
                className="worldtrend-chart"
                points={history.map((point) => point.mentionCount)}
                width={240}
                height={84}
                color="#4F46E5"
                filled
                gradientId="worldtrend-history"
              />
              <div className="worldtrend-chart-axis">
                <span>{formatDay(history[0].bucketStart)}</span>
                <span>{formatDay(history[history.length - 1].bucketStart)}</span>
              </div>
            </>
          )}
      </section>

      {/*
        * 순위와 경로가 보는 구간이 다릅니다. 밝히지 않으면 같은 구간의 숫자로 읽혀,
        * 순위에 없는 나라가 경로에 있는 것을 오류로 봅니다.
        */}
      {journeyRange && (
        <p className="worldtrend-note">
          확산 경로는 {formatDay(journeyRange.startDate)}부터 {formatDay(journeyRange.endDate)}까지 30일을 봅니다.
          위 순위는 {PERIOD_LABELS[period]} 기준이라 두 목록의 나라가 다를 수 있습니다.
        </p>
      )}
    </>
  );
}

export function GlobalTrendsPage() {
  const [domain, setDomain] = useState<string>();
  const [period, setPeriod] = useState<RegionPeriodCode>(DEFAULT_REGION_PERIOD);
  const [selectedTrendId, setSelectedTrendId] = useState<number>();
  const [mode, setMode] = useState<MapMode>('globe');
  /* 지도를 넓게 보고 싶을 때 양옆 칸을 접어 둘 수 있습니다. */
  const [folded, setFolded] = useState<Record<Panel, boolean>>({ left: false, right: false });

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

  const listQuery = useTrends(activeDomain
    ? { domain: activeDomain, type: 'CURRENT', period, page: 0, size: LIST_SIZE }
    : undefined);
  const trends = useMemo(() => listQuery.data?.trends ?? [], [listQuery.data]);

  // 분야나 기간을 바꿔 고른 키워드가 목록에서 사라지면 첫 키워드로 옮겨 갑니다.
  const trend = trends.find((item) => item.trendId === selectedTrendId) ?? trends[0];
  const trendId = trend?.trendId;

  const regionsQuery = useTrendRegions(trendId, period);
  const journeyQuery = useTrendRegionJourney(trendId);
  const regions = useMemo(() => regionsQuery.data?.regions ?? [], [regionsQuery.data]);
  const journey = useMemo(() => journeyQuery.data?.regions ?? [], [journeyQuery.data]);

  /*
   * 지도 정류장은 확산 경로에서 만듭니다. 순위가 아니라 처음 잡힌 순서여야 지도가 퍼져 나간
   * 길을 따라갑니다. 지도가 자리를 모르는 나라는 핀을 찍을 수 없어 빠집니다.
   */
  const stops = useMemo<MapStop[]>(() => {
    const mentionByCode = new Map(regions.map((region) => [region.countryCode, region.mentionCount]));
    return journey.flatMap((stop) => {
      const country = countryGeoOf(stop.countryCode);
      if (!country) return [];
      const mentionCount = mentionByCode.get(stop.countryCode) ?? 0;
      return [{
        country,
        weight: mentionCount,
        label: mentionCount > 0 ? `${formatCount(mentionCount)}건` : '최근 잠잠',
        since: formatDay(stop.firstDetectedDate),
      }];
    });
  }, [journey, regions]);

  const route = useMemo(() => stops.map((stop) => stop.country), [stops]);
  const tour = useSpreadTour(route, String(trendId ?? ''));

  const toggleFold = (panel: Panel) => setFolded((current) => ({ ...current, [panel]: !current[panel] }));

  // 고른 키워드가 밀려났으면 지금 보고 있는 것으로 상태를 맞춰 둡니다.
  useEffect(() => {
    if (trendId !== undefined && trendId !== selectedTrendId) setSelectedTrendId(trendId);
  }, [trendId, selectedTrendId]);

  const listLoading = domainsQuery.isLoading || listQuery.isLoading;
  const listFailed = domainsQuery.isError || listQuery.isError;
  const mappedOut = journey.length - stops.length;

  return (
    <div className={`worldtrend-page${folded.left ? ' is-left-folded' : ''}${folded.right ? ' is-right-folded' : ''}`}>
      <aside className="worldtrend-list">
        <div className="worldtrend-list-head">
          <h1>국가별 트렌드</h1>
          <p>키워드를 고르면 그 말이 퍼져 나간 길을 지도가 따라갑니다.</p>
        </div>

        <div className="worldtrend-chips">
          {domains.map((option) => (
            <button
              type="button"
              key={option.domain}
              className={`worldtrend-chip ${option.domain === activeDomain ? 'is-selected' : ''}`}
              onClick={() => setDomain(option.domain)}
            >
              {option.name}
            </button>
          ))}
        </div>

        {/* 국가별 조회는 24H·7D 만 받습니다. 30D 는 고를 수 없게 아예 내놓지 않습니다. */}
        <div className="worldtrend-chips">
          {REGION_PERIODS.map((code) => (
            <button
              type="button"
              key={code}
              className={`worldtrend-chip ${code === period ? 'is-selected' : ''}`}
              aria-pressed={code === period}
              onClick={() => setPeriod(code)}
            >
              {PERIOD_LABELS[code]}
            </button>
          ))}
        </div>

        {listLoading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}
        {!listLoading && listFailed && (
          <div className="trendin-state is-error" role="alert">
            <p>트렌드를 불러오지 못했습니다.</p>
            <button type="button" onClick={() => void (domainsQuery.isError ? domainsQuery.refetch() : listQuery.refetch())}>다시 시도</button>
          </div>
        )}
        {/*
          * 고른 분야가 없으면 지도에 올릴 키워드도 없습니다. '집계된 트렌드가 없다'고 하면
          * 서버 탓처럼 읽히므로, 무엇이 비었고 어디서 채우는지를 짚어 줍니다.
          */}
        {noChosenDomain && (
          <div className="trendin-state" role="status">
            <p>아직 고른 관심 분야가 없습니다.</p>
            <Link to="/mypage/profile">관심 분야 고르러 가기</Link>
          </div>
        )}
        {!listLoading && !listFailed && !noChosenDomain && trends.length === 0 && (
          <div className="trendin-state" role="status"><p>이 구간에 집계된 트렌드가 없습니다.</p></div>
        )}

        <ul className="worldtrend-items">
          {trends.map((item, index) => (
            <li key={item.trendId}>
              <button
                type="button"
                className={`worldtrend-item ${item.trendId === trendId ? 'is-selected' : ''}`}
                onClick={() => setSelectedTrendId(item.trendId)}
              >
                {/* 시안의 이모지 자리입니다. 서버가 주지 않는 그림 대신 순위를 세웁니다. */}
                <span className="worldtrend-item-emoji" aria-hidden="true">{item.rank ?? index + 1}</span>
                <span className="worldtrend-item-body">
                  <span className="worldtrend-item-name">{item.keyword}</span>
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
        <div className="worldtrend-map">
          <WorldMap
            mode={mode}
            view={tour.view}
            stops={stops}
            focusIndex={tour.focusIndex}
            stopIndex={tour.stopIndex}
            onPickStop={tour.goTo}
          />
          <div className="worldtrend-toolbar">
            <div className="worldtrend-modes">
              <button type="button" className={mode === 'globe' ? 'is-selected' : ''} onClick={() => setMode('globe')}>
                <GlobeIcon />
                지구본
              </button>
              <button type="button" className={mode === 'flat' ? 'is-selected' : ''} onClick={() => setMode('flat')}>
                <GridIcon />
                평면 지도
              </button>
            </div>

            <div className="worldtrend-tourbtns">
              <button type="button" disabled={stops.length < 2} onClick={tour.playing ? tour.pause : tour.play}>
                {tour.playing ? '멈춤' : '경로 따라가기'}
              </button>
              <button type="button" onClick={tour.showWorld}>전체 보기</button>
            </div>
          </div>
          <FoldTab side="left" folded={folded.left} onToggle={() => toggleFold('left')} />
          <FoldTab side="right" folded={folded.right} onToggle={() => toggleFold('right')} />
        </div>

        {/*
          * 확산 경로는 칸에 담지 않고 지도 아래쪽에 그대로 띄웁니다. 나라 수·언급량은 오른쪽
          * 요약에 이미 있어, 아래에 또 두면 같은 숫자를 두 번 읽게 됩니다.
          */}
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
                    onClick={() => tour.goTo(index)}
                  >
                    <span aria-hidden="true">{stop.country.flag}</span>
                    <span className="worldtrend-flow-name">{stop.country.name}</span>
                    <span className="worldtrend-flow-date">{stop.since}</span>
                  </button>
                </li>
              ))}
            </ol>
            {/* 지도에 못 올린 나라를 감추면 경로에서 빠진 것을 누락으로 읽습니다. */}
            {mappedOut > 0 && (
              <p className="worldtrend-flow-note">
                지도에 자리를 모르는 나라 {mappedOut}곳은 오른쪽 목록에만 있습니다.
              </p>
            )}
          </div>
        </div>
      </main>

      <aside className="worldtrend-side">
        {trend
          ? (
            <SummaryPanel
              trend={trend}
              period={period}
              regions={regions}
              regionsLoading={regionsQuery.isLoading}
              journey={journey}
              journeyRange={journeyQuery.data}
            />
          )
          : (
            <section className="worldtrend-card">
              <div className="worldtrend-card-head"><h2>글로벌 요약</h2></div>
              <p className="worldtrend-summary-lead">왼쪽에서 키워드를 고르면 그 말이 퍼져 나간 길을 보여 드립니다.</p>
            </section>
          )}
      </aside>
    </div>
  );
}
