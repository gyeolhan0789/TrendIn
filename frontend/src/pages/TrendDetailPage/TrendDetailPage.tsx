import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { HomePage } from '../HomePage/HomePage';
import { formatGrowth } from '../../features/trend/trendFormat';
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
import { ANALYSIS_PERIODS, parsePeriod, SAVED_TREND_PERIOD } from '../../constants/filterCodes';
import type { PeriodCode } from '../../constants/filterCodes';
import type { TrendDetailLocationState } from '../../features/trend/trendDetailLink';
import type { TrendDetail, TrendHistoryPoint } from '../../features/trend/types/trend';

const periodLabels: Record<PeriodCode, string> = { '24H': '24시간', '7D': '7일', '30D': '30일' };

/** 연관도는 0~100입니다. 높은 쪽만 색을 달리해 눈에 먼저 들어오게 합니다. */
const STRONG_RELATION_SCORE = 75;

/** 연관 키워드 한 쪽에 여덟 개. 칩이라 줄바꿈으로 흘러 이 정도가 서너 줄에 담깁니다. */
const KEYWORD_PAGE_SIZE = 8;

/** 시안은 최근 칸일수록 진하게 칠합니다. 마지막 칸이 지금 구간입니다. */
const RECENT_BAR_COUNT = 4;

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

function getChartBarColor(index: number, total: number) {
  if (index === total - 1) return '#1a5ecf';
  return index >= total - RECENT_BAR_COUNT ? '#93b5e8' : '#d0daf0';
}

function getKeywordStrength(relationScore: number) {
  return relationScore >= STRONG_RELATION_SCORE ? ' is-strong' : '';
}

function describeWindow(trend: TrendDetail) {
  const window = trend.analysisWindow;
  if (!window) return undefined;
  return `${formatMonthDay(window.recentStart)} ~ ${formatMonthDay(window.recentEnd)}`;
}

interface PagerProps {
  /** 읽어 줄 이름. 한 화면에 고르개가 둘이라 무엇을 넘기는지 밝혀야 합니다. */
  label: string;
  /** 0 부터 셉니다. 화면에는 1 부터 적습니다. */
  current: number;
  total: number;
  busy?: boolean;
  onPrev: () => void;
  onNext: () => void;
}

/** 양 끝에서 잠깁니다. 처음으로 돌아가지 않습니다 — 끝에 닿았다는 것이 화살표로 보여야 합니다. */
function Pager({ label, current, total, busy = false, onPrev, onNext }: PagerProps) {
  return (
    <div className="detail-pager" role="group" aria-label={label}>
      <button type="button" onClick={onPrev} disabled={current === 0} aria-label={`${label} 이전 쪽`}>←</button>
      <span>{current + 1} / {total}</span>
      <button
        type="button"
        onClick={onNext}
        disabled={busy || current + 1 >= total}
        aria-label={`${label} 다음 쪽`}
      >
        →
      </button>
    </div>
  );
}

export function TrendDetailPage() {
  const { trendId: trendIdParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const period = parsePeriod(searchParams.get('period')
    ?? (searchParams.get('from') === 'saved' ? SAVED_TREND_PERIOD : null));
  // 주소에 트렌드가 아닌 값이 들어올 수 있어, 숫자로 읽히지 않으면 조회하지 않습니다.
  const parsedTrendId = Number(trendIdParam);
  const trendId = Number.isInteger(parsedTrendId) && parsedTrendId > 0 ? parsedTrendId : undefined;

  /*
   * 상세는 보던 화면 위에 뜹니다. 어느 화면에서 열었는지는 링크가 함께 넘겨 주고, 그 화면은
   * 라우터가 뒤에 그대로 그립니다. 닫을 때는 앞으로 밀어 보내지 않고 왔던 자리로 되돌아갑니다.
   */
  const backgroundLocation = (location.state as TrendDetailLocationState | null)?.backgroundLocation;
  // 주소를 바로 열었으면 돌아갈 자리가 없습니다. 저장 목록에서 온 주소만 그리로 보내고 나머지는 대시보드입니다.
  const fromSaved = searchParams.get('from') === 'saved';
  const fallbackPath = fromSaved ? '/saved' : '/dashboard';
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

  /*
   * 기간은 주소에 적습니다. 새로고침이나 링크 공유에도 보던 기간이 그대로 열립니다.
   *
   * 두 가지를 지켜야 합니다. state 를 그대로 넘기지 않으면 backgroundLocation 이 사라져 뒤 화면이
   * 비고 닫기가 왔던 자리 대신 대시보드로 갑니다. 그리고 바꿔치기로 넣지 않으면 기간을 고를 때마다
   * 이력이 쌓여, 닫으려고 뒤로 가면 상세가 닫히는 대신 앞서 보던 기간으로 되돌아갑니다.
   */
  const selectPeriod = (next: PeriodCode) => {
    if (next === period) return;
    const params = new URLSearchParams(searchParams);
    params.set('period', next);
    setSearchParams(params, { replace: true, state: location.state });
  };

  const closeDrawer = useCallback(() => {
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    setIsClosing(true);
    closeTimerRef.current = window.setTimeout(() => {
      if (backgroundLocation) navigate(-1);
      else navigate(fallbackPath);
    }, 380);
  }, [backgroundLocation, fallbackPath, navigate]);

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

  const [sourcePage, setSourcePage] = useState(0);
  const [keywordPage, setKeywordPage] = useState(0);

  // 다른 트렌드를 열면 쪽을 처음으로 되돌립니다. 남겨 두면 세 번째 쪽부터 열립니다.
  useEffect(() => {
    setSourcePage(0);
    setKeywordPage(0);
  }, [trendId]);

  const history = useMemo(() => historyQuery.data?.history ?? [], [historyQuery.data]);
  const chartBars = useMemo(() => {
    const peak = Math.max(...history.map((point) => point.mentionCount), 0);
    return history.map((point, index) => ({
      label: formatBucketLabel(point, period),
      value: point.mentionCount,
      // 가장 큰 칸을 기준으로 높이를 잡습니다. 전부 0이면 아래에서 따로 안내합니다.
      height: peak > 0 ? (point.mentionCount / peak) * 100 : 0,
      color: getChartBarColor(index, history.length),
      // 왼쪽부터 차례로 올라오도록 조금씩 늦춥니다.
      delay: index * 30,
    }));
  }, [history, period]);
  const hasMentions = chartBars.some((bar) => bar.value > 0);

  const contentPages = useMemo(() => contentsQuery.data?.pages ?? [], [contentsQuery.data]);
  const contents = contentPages[sourcePage]?.content ?? [];
  /*
   * 쪽 수는 서버가 준 전체 개수로 셉니다. 받아 둔 쪽 수로 세면 앞으로 넘길 때마다 그 값이
   * 현재 쪽과 같아져 6 / 6+ 처럼 아무것도 말하지 못하는 숫자가 됩니다.
   * 쪽 크기는 응답이 알려 주므로 화면이 따로 알 필요가 없습니다.
   */
  const firstContentPage = contentPages[0];
  const sourcePageCount = firstContentPage && firstContentPage.size > 0
    ? Math.max(1, Math.ceil(firstContentPage.totalElements / firstContentPage.size))
    : 1;
  /* 타임라인은 처음 네 건을 짚는 자리입니다. 기사 쪽을 넘긴다고 따라 움직이면 안 됩니다. */
  const timeline = (contentPages[0]?.content ?? []).slice(0, 4);

  /*
   * 앞으로는 아직 안 받은 쪽이면 받아 오고, 뒤로는 이미 받아 둔 쪽이라 그냥 옮깁니다.
   * 받아 왔는데 쪽이 늘지 않았으면 옮기지 않습니다 — 빈 쪽을 펼치게 됩니다.
   */
  const goNextSource = () => {
    if (sourcePage + 1 < contentPages.length) {
      setSourcePage(sourcePage + 1);
      return;
    }
    if (!contentsQuery.hasNextPage || contentsQuery.isFetchingNextPage) return;
    void contentsQuery.fetchNextPage().then((result) => {
      if ((result.data?.pages.length ?? 0) > sourcePage + 1) setSourcePage(sourcePage + 1);
    });
  };

  const relatedKeywords = keywordsQuery.data ?? [];
  const keywordPageCount = Math.max(1, Math.ceil(relatedKeywords.length / KEYWORD_PAGE_SIZE));
  // 다시 받아 개수가 줄면 보던 쪽이 목록 밖으로 나갈 수 있어 마지막 쪽으로 당겨 둡니다.
  const currentKeywordPage = Math.min(keywordPage, keywordPageCount - 1);
  const visibleKeywords = relatedKeywords.slice(
    currentKeywordPage * KEYWORD_PAGE_SIZE,
    (currentKeywordPage + 1) * KEYWORD_PAGE_SIZE,
  );
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
            <button type="button" className="detail-back" onClick={closeDrawer} aria-label="상세 닫고 보던 화면으로">←</button>
            <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="detail-save" />
          </nav>

          <header className="detail-hero">
            <span className="detail-category">{trend.domain.name}</span>
            <h1>{trend.keyword}</h1>
            <p>{trend.description ?? '아직 정리된 설명이 없습니다.'}</p>
          </header>

          {/* 아래 지표와 차트가 모두 이 기간을 따릅니다. 원본 소스와 연관 키워드는 기간을 타지 않습니다. */}
          <div className="detail-periods" role="group" aria-label="집계 기간">
            {ANALYSIS_PERIODS.map((code) => (
              <button
                type="button"
                key={code}
                className={`detail-period${code === period ? ' is-selected' : ''}`}
                aria-pressed={code === period}
                onClick={() => selectPeriod(code)}
              >
                {periodLabels[code]}
              </button>
            ))}
          </div>

          <section className="detail-kpis" aria-label="트렌드 핵심 지표">
            <div><span>{periodLabel} 언급량</span><strong>{formatNumber(trend.mentionCount)}</strong></div>
            <div><span>직전 구간 대비</span><strong className="accent">{formatGrowth(trend.growthRate)}</strong></div>
            <div className="detail-kpi-meta">
              {windowLabel && <span><b>{windowLabel}</b> 집계</span>}
              <span>{trend.previousMentionCount === null ? '직전 구간 집계 없음' : `직전 구간 ${trend.previousMentionCount.toLocaleString()}건`}</span>
            </div>
          </section>

          <section className="detail-chart-card" aria-label={`${trend.keyword} 언급량 차트`}>
            <span className="detail-card-label">언급량 · 최근 {periodLabel}</span>
            {historyQuery.isLoading && <Skeleton count={2} />}
            {historyQuery.isError && <ErrorState message="언급량 추이를 불러오지 못했습니다." onRetry={() => historyQuery.refetch()} />}
            {historyQuery.isSuccess && !hasMentions && <EmptyState message="이 구간에 집계된 언급이 없습니다." />}
            {historyQuery.isSuccess && hasMentions && (
              <>
                <div className="detail-chart" role="img" aria-label={`${trend.keyword} 구간별 언급량`}>
                  {chartBars.map((bar) => (
                    <div className="detail-bar-track" key={bar.label} tabIndex={0} aria-label={`${bar.label} ${bar.value.toLocaleString()}건`}>
                      <span style={{ height: `${bar.height}%`, background: bar.color, animationDelay: `${bar.delay}ms` }}>
                        <b className="detail-bar-tooltip"><span>{bar.value.toLocaleString()}건</span><small>{bar.label}</small></b>
                      </span>
                    </div>
                  ))}
                </div>
                {/* 시안처럼 처음·가운데·끝만 짚어 줍니다. 칸이 둘뿐이면 가운데가 없습니다. */}
                <div className="chart-axis">
                  <span>{chartBars[0].label}</span>
                  {chartBars.length > 2 && <span>{chartBars[Math.floor((chartBars.length - 1) / 2)].label}</span>}
                  <span>{chartBars[chartBars.length - 1].label}</span>
                </div>
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
            <div className="detail-section-title">
              <h2>키워드가 언급된 원본 소스</h2>
              {contents.length > 0 && (
                <Pager
                  label="원본 소스"
                  current={sourcePage}
                  total={sourcePageCount}
                  busy={contentsQuery.isFetchingNextPage}
                  onPrev={() => setSourcePage(sourcePage - 1)}
                  onNext={goNextSource}
                />
              )}
            </div>
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
          </section>

          <section className="detail-related">
            <div className="detail-section-title">
              <h2>연관 키워드</h2>
              {relatedKeywords.length > KEYWORD_PAGE_SIZE && (
                <Pager
                  label="연관 키워드"
                  current={currentKeywordPage}
                  total={keywordPageCount}
                  onPrev={() => setKeywordPage(currentKeywordPage - 1)}
                  onNext={() => setKeywordPage(currentKeywordPage + 1)}
                />
              )}
            </div>
            {keywordsQuery.isLoading && <Skeleton count={1} />}
            {keywordsQuery.isError && <ErrorState onRetry={() => keywordsQuery.refetch()} />}
            {keywordsQuery.isSuccess && relatedKeywords.length === 0 && <EmptyState />}
            {relatedKeywords.length > 0 && (
              <div className="detail-keyword-list">
                {visibleKeywords.map((keyword) => (
                  <span className={`detail-keyword${getKeywordStrength(keyword.relationScore)}`} key={keyword.keywordId}>
                    <b>{keyword.keyword}</b>
                    <i title={`연관도 ${keyword.relationScore}점`}>{Math.round(keyword.relationScore)}</i>
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
                  <div className={`timeline-event${index === 0 ? ' is-important' : ''}`} key={content.contentId}>
                    <span className="timeline-dot" />
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

          <footer className="detail-foot">공개된 글을 모아 자동으로 정리한 분석입니다 · TrendIn</footer>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* 뒤 화면은 라우터가 그립니다. 주소를 바로 열어 뒤가 비어 있을 때만 여기서 기본 화면을 세웁니다. */}
      {!backgroundLocation && <div className="drawer-background" aria-hidden="true">{fromSaved ? <SavedTrendPage /> : <HomePage />}</div>}
      <div className={`modal-backdrop${isClosing ? ' is-closing' : ''}`} onClick={(event) => { if (event.target === event.currentTarget) closeDrawer(); }}>
        <aside ref={drawerRef} className={`detail-drawer${isClosing ? ' is-closing' : ''}`} role="dialog" aria-modal="true" aria-label="트렌드 상세" tabIndex={-1}>
          <div className="detail-drawer-content">{drawerContent}</div>
        </aside>
      </div>
    </>
  );
}
