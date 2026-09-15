import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { HomePage } from '../HomePage/HomePage';
import { SavedTrendPage } from '../SavedTrendPage/SavedTrendPage';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { Skeleton } from '../../components/common/Skeleton';
import { AddInterestKeywordButton } from '../../features/myPage/components/AddInterestKeywordButton';
import { BookmarkButton } from '../../features/savedTrend/components/BookmarkButton';
import { useTrendContents } from '../../features/trend/hooks/useTrendContents';
import { useTrendDetail } from '../../features/trend/hooks/useTrendDetail';
import { useTrendHistory } from '../../features/trend/hooks/useTrendHistory';
import { useTrendRelatedKeywords } from '../../features/trend/hooks/useTrendRelatedKeywords';
import { parsePeriod } from '../../constants/filterCodes';
import type { PeriodCode } from '../../constants/filterCodes';
import type { TrendDetail, TrendHistoryPoint } from '../../features/trend/types/trend';

const periodLabels: Record<PeriodCode, string> = { '24H': '24시간', '7D': '7일', '30D': '30일' };

/** 연관도는 0~100입니다. 높은 쪽을 굵게 보여 주려고 두 단으로 나눕니다. */
const STRONG_RELATION_SCORE = 75;
const MEDIUM_RELATION_SCORE = 60;

/*
 * 서버가 주는 시각은 Asia/Seoul 기준입니다. 보는 사람의 시간대로 바꾸면 자정 경계가 어긋나
 * 헷갈리므로, 받은 문자열에서 필요한 자리만 잘라 씁니다.
 */
function formatMonthDay(value?: string) {
  const match = value ? /^(\d{4})-(\d{2})-(\d{2})/.exec(value) : null;
  return match ? `${match[2]}.${match[3]}` : undefined;
}

function formatHour(value: string) {
  const match = /T(\d{2}):/.exec(value);
  return match ? `${Number(match[1])}시` : value;
}

function formatBucketLabel(point: TrendHistoryPoint, period: PeriodCode) {
  return period === '24H' ? formatHour(point.bucketStart) : formatMonthDay(point.bucketStart) ?? point.bucketStart;
}

function formatNumber(value: number | null) {
  return value === null ? '—' : value.toLocaleString();
}

function formatGrowthRate(value: number | null) {
  return value === null ? '—' : `${value > 0 ? '+' : ''}${value}%`;
}

function getChartBarGradient(index: number, total: number) {
  const progress = total > 1 ? index / (total - 1) : 1;
  const saturation = Math.round(48 + progress * 24);
  const bottomLightness = Math.round(91 - progress * 46);
  const topLightness = Math.min(96, bottomLightness + 8);
  return `linear-gradient(180deg, hsl(220 ${saturation}% ${topLightness}%), hsl(220 ${saturation}% ${bottomLightness}%))`;
}

function getKeywordStrength(relationScore: number) {
  if (relationScore >= STRONG_RELATION_SCORE) return ' is-strong';
  if (relationScore >= MEDIUM_RELATION_SCORE) return ' is-medium';
  return '';
}

function describeWindow(trend: TrendDetail) {
  const window = trend.analysisWindow;
  if (!window) return undefined;
  return `${formatMonthDay(window.recentStart)} ~ ${formatMonthDay(window.recentEnd)}`;
}

export function TrendDetailPage() {
  const { trendId: trendIdParam } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const period = parsePeriod(searchParams.get('period'));
  // 주소에 트렌드가 아닌 값이 들어올 수 있어, 숫자로 읽히지 않으면 조회하지 않습니다.
  const parsedTrendId = Number(trendIdParam);
  const trendId = Number.isInteger(parsedTrendId) && parsedTrendId > 0 ? parsedTrendId : undefined;

  // 저장 페이지에서 열었을 때는 목록 위에 드로어를 띄우고, 닫으면 다시 목록으로 돌아갑니다.
  const fromSaved = searchParams.get('from') === 'saved';
  const homePath = fromSaved ? '/saved' : `/${searchParams.toString() ? `?${searchParams.toString()}` : ''}`;
  const drawerRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const isClosingRef = useRef(false);
  const [isClosing, setIsClosing] = useState(false);

  const detailQuery = useTrendDetail(trendId, period);
  const historyQuery = useTrendHistory(trendId, period);
  const keywordsQuery = useTrendRelatedKeywords(trendId);
  const contentsQuery = useTrendContents(trendId);
  const trend = detailQuery.data;
  const periodLabel = periodLabels[period];

  const closeDrawer = useCallback(() => {
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    setIsClosing(true);
    closeTimerRef.current = window.setTimeout(() => navigate(homePath), 380);
  }, [homePath, navigate]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeDrawer();
    };

    document.body.style.overflow = 'hidden';
    drawerRef.current?.focus();
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [closeDrawer]);

  useEffect(() => () => {
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
  }, []);

  const history = useMemo(() => historyQuery.data?.history ?? [], [historyQuery.data]);
  const chartBars = useMemo(() => {
    const peak = Math.max(...history.map((point) => point.mentionCount), 0);
    return history.map((point, index) => ({
      label: formatBucketLabel(point, period),
      value: point.mentionCount,
      // 가장 큰 칸을 기준으로 높이를 잡습니다. 전부 0이면 아래에서 따로 안내합니다.
      height: peak > 0 ? (point.mentionCount / peak) * 100 : 0,
      isPeak: peak > 0 && point.mentionCount === peak,
      gradient: getChartBarGradient(index, history.length),
    }));
  }, [history, period]);
  const hasMentions = chartBars.some((bar) => bar.value > 0);

  const contents = useMemo(
    () => contentsQuery.data?.pages.flatMap((page) => page.content) ?? [],
    [contentsQuery.data],
  );
  const relatedKeywords = keywordsQuery.data ?? [];
  const timeline = contents.slice(0, 4);
  const windowLabel = trend ? describeWindow(trend) : undefined;

  let drawerContent: ReactNode;
  if (!trendId || detailQuery.isError) {
    drawerContent = <ErrorState message="트렌드 정보를 불러오지 못했습니다." onRetry={() => detailQuery.refetch()} />;
  } else if (detailQuery.isLoading) {
    drawerContent = <Skeleton count={5} />;
  } else if (!trend) {
    drawerContent = <EmptyState />;
  } else {
    drawerContent = (
      <div className="detail-page detail-page--drawer">
        <div className="detail-page-inner">
          <nav className="detail-nav" aria-label="상세페이지 메뉴">
            <Link className="detail-back" to={homePath} aria-label={fromSaved ? '저장한 트렌드로 돌아가기' : '홈으로 돌아가기'}>←</Link>
            <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="detail-save" />
          </nav>

          <header className="detail-hero">
            <span className="detail-category">{trend.domain.name}</span>
            <h1>{trend.keyword}</h1>
            <p>{trend.description}</p>
          </header>

          <section className="detail-kpis" aria-label="트렌드 핵심 지표">
            <div><span>{periodLabel} 언급량</span><strong>{formatNumber(trend.mentionCount)}</strong></div>
            <div><span>직전 구간 대비</span><strong className="accent">{formatGrowthRate(trend.growthRate)}</strong></div>
            <div><span>직전 구간 언급량</span><strong>{formatNumber(trend.previousMentionCount)}</strong></div>
          </section>

          {windowLabel && <p className="detail-card-label">{windowLabel} 집계 · 직전 같은 길이의 구간과 비교</p>}

          <section className="detail-chart-card" aria-label={`${trend.keyword} 언급량 차트`}>
            <span className="detail-card-label">언급량 그래프</span>
            {historyQuery.isLoading && <Skeleton count={2} />}
            {historyQuery.isError && <ErrorState message="언급량 추이를 불러오지 못했습니다." onRetry={() => historyQuery.refetch()} />}
            {historyQuery.isSuccess && !hasMentions && <EmptyState message="이 구간에 집계된 언급이 없습니다." />}
            {historyQuery.isSuccess && hasMentions && (
              <>
                <div className="detail-chart detail-chart--reference" role="img" aria-label={`${trend.keyword} 구간별 언급량`}>
                  {chartBars.map((bar) => (
                    <div className="detail-bar-track" key={bar.label} tabIndex={0} aria-label={`${bar.label} ${bar.value.toLocaleString()}건`}>
                      <span className={bar.isPeak ? 'is-current' : ''} style={{ height: `${bar.height}%`, background: bar.gradient }}>
                        <b className="detail-bar-tooltip"><span>{bar.value.toLocaleString()}건</span><small>{bar.label}</small></b>
                      </span>
                    </div>
                  ))}
                </div>
                <div className="chart-axis chart-axis--reference"><span>{chartBars[0]?.label}</span><span>{chartBars.at(-1)?.label}</span></div>
              </>
            )}
          </section>

          <section className="detail-why-now">
            <span className="detail-card-label">지금 뜨는 이유</span>
            {trend.summary && <p className="detail-why-summary">{trend.summary}</p>}
            {trend.reason && <p className="detail-why-description">{trend.reason}</p>}
            {!trend.summary && !trend.reason && <p className="detail-why-description">아직 정리된 설명이 없습니다.</p>}
          </section>

          <section className="detail-sources">
            <div className="detail-section-title"><h2>키워드가 언급된 원본 소스</h2><span>{contents.length}건{contentsQuery.hasNextPage ? '+' : ''}</span></div>
            {contentsQuery.isLoading && <Skeleton count={4} />}
            {contentsQuery.isError && <ErrorState onRetry={() => contentsQuery.refetch()} />}
            {contentsQuery.isSuccess && contents.length === 0 && <EmptyState />}
            {contents.map((content, index) => (
              <a className="detail-source" href={content.url} target="_blank" rel="noreferrer" key={content.contentId}>
                <span className="detail-source-number">{String(index + 1).padStart(2, '0')}</span>
                <span className="detail-source-copy">
                  <strong>{content.title}</strong>
                  <span><b>{content.source}</b><i>·</i>{formatMonthDay(content.publishedAt) ?? content.publishedAt}</span>
                </span>
                <span className="detail-source-arrow">↗</span>
              </a>
            ))}
            {contentsQuery.hasNextPage && (
              <button type="button" className="detail-more" disabled={contentsQuery.isFetchingNextPage} onClick={() => void contentsQuery.fetchNextPage()}>
                {contentsQuery.isFetchingNextPage ? '불러오는 중…' : '+ 더보기'}
              </button>
            )}
          </section>

          <section className="detail-related">
            <div className="detail-section-title"><h2>연관 키워드</h2></div>
            {keywordsQuery.isLoading && <Skeleton count={1} />}
            {keywordsQuery.isError && <ErrorState onRetry={() => keywordsQuery.refetch()} />}
            {keywordsQuery.isSuccess && relatedKeywords.length === 0 && <EmptyState />}
            {relatedKeywords.length > 0 && (
              <div className="detail-keyword-list">
                {relatedKeywords.map((keyword) => (
                  <span className={`detail-keyword${getKeywordStrength(keyword.relationScore)}`} key={keyword.keywordId}>
                    <b>{keyword.keyword}</b>
                    <AddInterestKeywordButton keywordId={keyword.keywordId} keyword={keyword.keyword} />
                  </span>
                ))}
              </div>
            )}
          </section>

          <section className="detail-timeline">
            <div className="detail-section-title"><h2>타임라인</h2></div>
            {timeline.length === 0 && !contentsQuery.isLoading && <EmptyState />}
            {timeline.length > 0 && (
              <div className="timeline-list">
                {timeline.map((content, index) => (
                  <div className="timeline-event" key={content.contentId}>
                    <span className={`timeline-dot${index === 0 ? ' is-important' : ''}`} />
                    <time>{formatMonthDay(content.publishedAt) ?? content.publishedAt}</time>
                    <div>
                      <p>{content.title}</p>
                      <a href={content.url} target="_blank" rel="noreferrer">{content.source} ↗</a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

        </div>
      </div>
    );
  }

  return (
    <>
      <div className="drawer-background" aria-hidden="true">{fromSaved ? <SavedTrendPage /> : <HomePage />}</div>
      <div className={`modal-backdrop${isClosing ? ' is-closing' : ''}`} onClick={(event) => { if (event.target === event.currentTarget) closeDrawer(); }}>
        <aside ref={drawerRef} className={`detail-drawer${isClosing ? ' is-closing' : ''}`} role="dialog" aria-modal="true" aria-label="트렌드 상세" tabIndex={-1}>
          <div className="detail-drawer-content">{drawerContent}</div>
        </aside>
      </div>
    </>
  );
}
