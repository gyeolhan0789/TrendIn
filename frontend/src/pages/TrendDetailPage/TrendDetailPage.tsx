import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { HomePage } from '../HomePage/HomePage';
import { SavedTrendPage } from '../SavedTrendPage/SavedTrendPage';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { Skeleton } from '../../components/common/Skeleton';
import { useTrendAnalysis } from '../../features/trend/hooks/useTrendAnalysis';
import { useTrendDetail } from '../../features/trend/hooks/useTrendDetail';
import { useRelatedKeywords } from '../../features/trend/hooks/useRelatedKeywords';
import { useRelatedContents } from '../../features/trend/hooks/useRelatedContents';
import { useSaveTrend } from '../../features/savedTrend/hooks/useSaveTrend';
import { AddInterestKeywordButton } from '../../features/myPage/components/AddInterestKeywordButton';

const periodLabels: Record<string, string> = { '24h': '24시간', '7d': '7일', '30d': '30일' };
const chartShape = [18, 21, 25, 23, 31, 29, 38, 35, 47, 44, 58, 67, 74, 88];

function formatMonthDay(value?: string) {
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[2]}.${match[3]}` : undefined;
}

function getChartDays(endDate?: string) {
  if (!endDate) return [];
  const end = new Date(endDate);
  if (Number.isNaN(end.getTime())) return [];

  return chartShape.map((_, index) => {
    const date = new Date(end);
    date.setDate(date.getDate() - (chartShape.length - 1 - index));
    return formatMonthDay(date.toISOString());
  });
}

function getChartBarGradient(index: number) {
  const progress = index / (chartShape.length - 1);
  const saturation = Math.round(48 + progress * 24);
  const bottomLightness = Math.round(91 - progress * 46);
  const topLightness = Math.min(96, bottomLightness + 8);
  return `linear-gradient(180deg, hsl(220 ${saturation}% ${topLightness}%), hsl(220 ${saturation}% ${bottomLightness}%))`;
}

function getKeywordStrength(relevance?: number) {
  if ((relevance ?? 0) >= 0.75) return ' is-strong';
  if ((relevance ?? 0) >= 0.6) return ' is-medium';
  return '';
}

export function TrendDetailPage() {
  const { trendId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const period = searchParams.get('period') ?? '24h';
  // 저장 페이지에서 열었을 때는 목록 위에 드로어를 띄우고, 닫으면 다시 목록으로 돌아갑니다.
  const fromSaved = searchParams.get('from') === 'saved';
  const homePath = fromSaved ? '/saved' : `/${searchParams.toString() ? `?${searchParams.toString()}` : ''}`;
  const drawerRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const isClosingRef = useRef(false);
  const [isClosing, setIsClosing] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const detailQuery = useTrendDetail(trendId);
  const analysisQuery = useTrendAnalysis(trendId);
  const keywordsQuery = useRelatedKeywords(trendId);
  const contentsQuery = useRelatedContents(trendId);
  const saveMutation = useSaveTrend();
  const trend = detailQuery.data;
  const periodLabel = periodLabels[period] ?? period;
  const detailSearch = searchParams.toString() ? `?${searchParams.toString()}` : '';
  const firstDetectedLabel = formatMonthDay(trend?.firstDetectedAt) ?? '--.--';
  const chartDays = useMemo(() => getChartDays(trend?.updatedAt ?? trend?.firstDetectedAt), [trend?.firstDetectedAt, trend?.updatedAt]);

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

  const chartBars = useMemo(() => {
    if (!trend) return [];
    const growthFactor = Math.max(0.55, Math.min(1.55, 1 + trend.growthRate / 300));
    return chartShape.map((value, index) => ({
      day: chartDays[index],
      value: Math.round(value * growthFactor),
      height: Math.min(100, value * growthFactor),
      color: index === chartShape.length - 1 ? 'is-current' : index >= chartShape.length - 4 ? 'is-recent' : '',
    }));
  }, [chartDays, trend]);

  useEffect(() => {
    if (saveMutation.isSuccess) setIsSaved(true);
  }, [saveMutation.isSuccess]);

  const contents = contentsQuery.data ?? [];
  const relatedKeywords = keywordsQuery.data ?? [];
  const timeline = contents.slice(0, 4);
  const handleSave = () => {
    if (trend && !isSaved && !saveMutation.isPending) saveMutation.mutate(trend.trendId);
  };

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
            <button type="button" className={`detail-save${isSaved ? ' is-saved' : ''}`} onClick={handleSave} aria-label={isSaved ? '저장됨' : '트렌드 저장'} title={isSaved ? '저장됨' : '트렌드 저장'} aria-pressed={isSaved} disabled={isSaved || saveMutation.isPending}>{isSaved ? '★' : '☆'}</button>
          </nav>

          <header className="detail-hero">
            <span className={`detail-category${trend.category === '패션' ? ' detail-category--fashion' : ''}`}>{trend.category}</span>
            <h1>{trend.keyword}</h1>
            <p>{trend.description ?? '트렌드 설명이 준비 중입니다.'}</p>
          </header>

          <section className="detail-kpis" aria-label="트렌드 핵심 지표">
            <div><span>총 언급량</span><strong>{trend.mentionCount.toLocaleString()}</strong></div>
            <div><span>{periodLabel} 변화</span><strong className="accent">+{trend.growthRate}%</strong></div>
            <div className="detail-trend-visual" role="img" aria-label={`${firstDetectedLabel}부터 현재까지의 추이`}>
              <div className="detail-trend-line" aria-hidden="true">
                <span className="detail-trend-point detail-trend-point--start" />
                <span className="detail-trend-point detail-trend-point--current" />
                <svg className="detail-trend-arrow" viewBox="0 0 22 16" aria-hidden="true"><path d="m2 14 6-6 4 4 8-10M14 2h6v6" /></svg>
              </div>
              <div className="detail-trend-labels" aria-hidden="true"><span>{firstDetectedLabel}</span><span>NOW</span></div>
            </div>
          </section>

          <section className="detail-chart-card" aria-label={`${trend.keyword} 언급량 차트`}>
            <span className="detail-card-label">언급량 그래프</span>
            <div className="detail-chart detail-chart--reference" role="img" aria-label={`${trend.keyword} 상대 언급 지수`}>
              {chartBars.map((bar, index) => <div className="detail-bar-track" key={bar.day ?? index} tabIndex={0} aria-label={`${bar.day ?? '날짜 정보 없음'} ${bar.value.toLocaleString()}건`}><span className={bar.color} style={{ height: `${bar.height}%`, background: getChartBarGradient(index), animationDelay: `${0.48 + index * 0.055}s` }}><b className="detail-bar-tooltip"><span>{bar.value.toLocaleString()}건</span><small>{bar.day ?? '날짜 정보 없음'}</small></b></span></div>)}
            </div>
            <div className="chart-axis chart-axis--reference"><span>{chartBars[0]?.day}</span><span>{chartBars.at(-1)?.day}</span></div>
          </section>

          <section className="detail-why-now">
            <span className="detail-card-label">지금 뜨는 이유</span>
            {analysisQuery.isLoading && <Skeleton count={1} />}
            {analysisQuery.isError && <ErrorState onRetry={() => analysisQuery.refetch()} />}
            {analysisQuery.data && <><p className="detail-why-summary">{analysisQuery.data.reason ?? analysisQuery.data.description}</p><p className="detail-why-description">{analysisQuery.data.description}</p></>}
          </section>

          <section className="detail-sources">
            <div className="detail-section-title"><h2>키워드가 언급된 원본 소스</h2><span>{contentsQuery.data?.length ?? 0}건</span></div>
            {contentsQuery.isLoading && <Skeleton count={4} />}
            {contentsQuery.isError && <ErrorState onRetry={() => contentsQuery.refetch()} />}
            {contents.length === 0 && !contentsQuery.isLoading && !contentsQuery.isError && <EmptyState />}
            {contents.slice(0, 4).map((content, index) => <a className="detail-source" href={content.url} target="_blank" rel="noreferrer" key={content.contentId}><span className="detail-source-number">{String(index + 1).padStart(2, '0')}</span><span className="detail-source-copy"><strong>{content.title}</strong><span><b>{content.source ?? '출처 미정'}</b><i>·</i>{content.publishedAt ?? '게시일 미정'}</span></span><span className="detail-source-arrow">↗</span></a>)}
            {contents.length > 4 && <button type="button" className="detail-more">+ {contents.length - 4}건 더보기</button>}
          </section>

          <section className="detail-related">
            <div className="detail-section-title"><h2>연관 키워드</h2></div>
            {keywordsQuery.isLoading && <Skeleton count={1} />}
            {keywordsQuery.isError && <ErrorState onRetry={() => keywordsQuery.refetch()} />}
            {relatedKeywords.length === 0 && !keywordsQuery.isLoading && !keywordsQuery.isError && <EmptyState />}
            {relatedKeywords.length > 0 && <div className="detail-keyword-list">{relatedKeywords.map((keyword) => <span className={`detail-keyword${getKeywordStrength(keyword.relevance)}`} key={keyword.trendId ?? keyword.keywordId ?? keyword.keyword}><Link to={{ pathname: `/trends/${keyword.trendId ?? keyword.keywordId ?? encodeURIComponent(keyword.keyword)}`, search: detailSearch }}><b>{keyword.keyword}</b></Link><AddInterestKeywordButton keyword={keyword.keyword} trendId={keyword.trendId} /></span>)}</div>}
          </section>

          <section className="detail-timeline">
            <div className="detail-section-title"><h2>타임라인</h2></div>
            {timeline.length === 0 && !contentsQuery.isLoading && <EmptyState />}
            {timeline.length > 0 && <div className="timeline-list">{timeline.map((content, index) => <div className="timeline-event" key={content.contentId}><span className={`timeline-dot${index === 0 ? ' is-important' : ''}`} /><time>{formatMonthDay(content.publishedAt) ?? '게시일 미정'}</time><div><p>{content.title}</p><a href={content.url} target="_blank" rel="noreferrer">{content.source ?? '원본 소스'} ↗</a></div></div>)}</div>}
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
