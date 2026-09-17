import { useMemo, useState } from 'react';
import { WorldMap } from '../../features/globalTrend/components/WorldMap';
import type { MapMode } from '../../features/globalTrend/components/WorldMap';
import { DOMAIN_FILTERS, GLOBAL_TRENDS, countryOf } from '../../features/globalTrend/globalTrendSample';
import type { GlobalTrend } from '../../features/globalTrend/globalTrendSample';
import { useSpreadTour } from '../../features/globalTrend/hooks/useSpreadTour';
import { TrendSparkline } from '../../features/trend/components/TrendSparkline';

/*
 * 국가별 트렌드. 키워드 하나를 고르면 그 말이 어느 나라에서 시작해 어디로 이어졌는지,
 * 지도가 그 나라를 차례로 확대하며 따라갑니다.
 *
 * 화면은 한 화면 안에서 끝납니다. 지도는 창 크기에 맞춰 늘어나고, 스크롤은 왼쪽 목록과
 * 오른쪽 요약 안에서만 생깁니다. 지도를 보다가 아래로 밀려나면 흐름이 끊기기 때문입니다.
 *
 * 나라 수치는 아직 서버에 없는 표본입니다. 자세한 사정은 globalTrendSample.ts 에 적어 두었습니다.
 */

function growthTone(growth: number) {
  if (growth >= 100) return 'is-hot';
  if (growth > 0) return 'is-up';
  return 'is-down';
}

function growthText(growth: number) {
  return `${growth > 0 ? '+' : ''}${growth}%`;
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

function SummaryPanel({ trend }: { trend: GlobalTrend }) {
  const ranked = [...trend.spread].sort((a, b) => b.growth - a.growth);
  const top = Math.max(...ranked.map((stop) => Math.abs(stop.growth)));

  return (
    <>
      <section className="worldtrend-card">
        <div className="worldtrend-card-head">
          <h2>글로벌 요약</h2>
          <span className="worldtrend-card-note">{trend.since} 기준</span>
        </div>
        <h3 className="worldtrend-summary-title">{trend.keyword}</h3>
        <p className="worldtrend-summary-lead">{trend.summary}</p>
        <dl className="worldtrend-facts">
          <div>
            <dt>언급된 나라</dt>
            <dd>{trend.countries}개국</dd>
          </div>
          <div>
            <dt>전체 언급량</dt>
            <dd>{trend.mentions.toLocaleString()}건</dd>
          </div>
          <div>
            <dt>수집 콘텐츠</dt>
            <dd>{trend.contents.toLocaleString()}건</dd>
          </div>
        </dl>
      </section>

      <section className="worldtrend-card">
        <div className="worldtrend-card-head">
          <h2>국가별 관심도</h2>
          <span className="worldtrend-card-note">상위 {ranked.length}개국</span>
        </div>
        <ol className="worldtrend-rank">
          {ranked.map((stop, index) => {
            const country = countryOf(stop.country);
            return (
              <li key={stop.country}>
                <div className="worldtrend-rank-row">
                  <span className={`worldtrend-rank-no ${index < 3 ? 'is-top' : ''}`}>{index + 1}</span>
                  <span className="worldtrend-rank-flag" aria-hidden="true">{country.flag}</span>
                  <span className="worldtrend-rank-name">{country.name}</span>
                  <span className={`worldtrend-rank-growth ${growthTone(stop.growth)}`}>{growthText(stop.growth)}</span>
                </div>
                <div className="worldtrend-rank-bar">
                  <span style={{ width: `${Math.round((Math.abs(stop.growth) / top) * 100)}%` }} />
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="worldtrend-card worldtrend-card--chart">
        <div className="worldtrend-card-head">
          <h2>관심도 변화 추이</h2>
          <span className="worldtrend-card-note">최근 18일</span>
        </div>
        <TrendSparkline
          className="worldtrend-chart"
          points={trend.history}
          width={240}
          height={84}
          color="#4F46E5"
          filled
          gradientId="worldtrend-history"
        />
        <div className="worldtrend-chart-axis">
          <span>{trend.since.slice(5)}</span>
          <span>오늘</span>
        </div>
      </section>
    </>
  );
}

export function GlobalTrendsPage() {
  const [domain, setDomain] = useState(DOMAIN_FILTERS[0]);
  const [selectedId, setSelectedId] = useState(GLOBAL_TRENDS[0].id);
  const [mode, setMode] = useState<MapMode>('globe');
  /* 지도를 넓게 보고 싶을 때 양옆과 아래 칸을 접어 둘 수 있습니다. */
  const [folded, setFolded] = useState<Record<Panel, boolean>>({ left: false, right: false });

  const toggleFold = (panel: Panel) => setFolded((current) => ({ ...current, [panel]: !current[panel] }));

  const visibleTrends = useMemo(() => GLOBAL_TRENDS.filter((trend) => trend.domain === domain), [domain]);

  // 분야를 바꿔 고른 키워드가 목록에서 사라지면, 그 분야의 첫 키워드로 옮겨 갑니다.
  const trend = visibleTrends.find((item) => item.id === selectedId) ?? visibleTrends[0] ?? GLOBAL_TRENDS[0];

  const stops = useMemo(
    () => trend.spread.map((stop) => ({ country: countryOf(stop.country), growth: stop.growth, since: stop.since })),
    [trend],
  );

  const route = useMemo(() => stops.map((stop) => stop.country), [stops]);
  const tour = useSpreadTour(route, trend.id);

  return (
    <div className={`worldtrend-page${folded.left ? ' is-left-folded' : ''}${folded.right ? ' is-right-folded' : ''}`}>
      <aside className="worldtrend-list">
        <div className="worldtrend-list-head">
          <h1>국가별 트렌드</h1>
          <p>키워드를 고르면 그 말이 퍼져 나간 길을 지도가 따라갑니다.</p>
        </div>

        <div className="worldtrend-chips">
          {DOMAIN_FILTERS.map((name) => (
            <button
              type="button"
              key={name}
              className={`worldtrend-chip ${name === domain ? 'is-selected' : ''}`}
              onClick={() => setDomain(name)}
            >
              {name}
            </button>
          ))}
        </div>

        <ul className="worldtrend-items">
          {visibleTrends.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`worldtrend-item ${item.id === trend.id ? 'is-selected' : ''}`}
                onClick={() => setSelectedId(item.id)}
              >
                <span className="worldtrend-item-emoji" aria-hidden="true">{item.emoji}</span>
                <span className="worldtrend-item-body">
                  <span className="worldtrend-item-name">{item.keyword}</span>
                  <span className="worldtrend-item-meta">
                    <span className="worldtrend-item-domain">{item.domain}</span>
                    <span>{item.countries}개국</span>
                  </span>
                  <span className="worldtrend-item-trail">
                    <TrendSparkline points={item.history} width={56} height={16} color={item.growth < 0 ? '#9ca3af' : '#4F46E5'} />
                    <span className={`worldtrend-item-growth ${growthTone(item.growth)}`}>{growthText(item.growth)}</span>
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
              <button type="button" onClick={tour.playing ? tour.pause : tour.play}>
                {tour.playing ? '멈춤' : '경로 따라가기'}
              </button>
              <button type="button" onClick={tour.showWorld}>전체 보기</button>
            </div>
          </div>
          <FoldTab side="left" folded={folded.left} onToggle={() => toggleFold('left')} />
          <FoldTab side="right" folded={folded.right} onToggle={() => toggleFold('right')} />
        </div>

        {/*
          * 확산 경로는 칸에 담지 않고 지도 아래쪽에 그대로 띄웁니다. 나라 수·증가율·언급량은
          * 오른쪽 요약에 이미 있어, 아래에 또 두면 같은 숫자를 두 번 읽게 됩니다.
          */}
        <div className="worldtrend-flow">
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
        </div>
      </main>

      <aside className="worldtrend-side">
        <SummaryPanel trend={trend} />
      </aside>
    </div>
  );
}
