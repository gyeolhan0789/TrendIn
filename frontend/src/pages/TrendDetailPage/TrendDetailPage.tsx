import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { HomePage } from '../HomePage/HomePage';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { Skeleton } from '../../components/common/Skeleton';
import { useTrendAnalysis } from '../../features/trend/hooks/useTrendAnalysis';
import { useTrendDetail } from '../../features/trend/hooks/useTrendDetail';
import { useRelatedKeywords } from '../../features/trend/hooks/useRelatedKeywords';
import { useRelatedContents } from '../../features/trend/hooks/useRelatedContents';

const exampleBars = [18, 23, 19, 30, 28, 36, 32, 42, 45, 41, 57, 63, 69, 86];
const periodLabels: Record<string, string> = { '24h': '24시간', '7d': '7일', '30d': '30일' };

export function TrendDetailPage() {
  const { trendId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const period = searchParams.get('period') ?? '24h';
  const homePath = `/${searchParams.toString() ? `?${searchParams.toString()}` : ''}`;
  const drawerRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const isClosingRef = useRef(false);
  const [isClosing, setIsClosing] = useState(false);
  const detailQuery = useTrendDetail(trendId);
  const analysisQuery = useTrendAnalysis(trendId);
  const keywordsQuery = useRelatedKeywords(trendId);
  const contentsQuery = useRelatedContents(trendId);

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
    closeButtonRef.current?.focus();
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

  let drawerContent: ReactNode;

  if (!trendId || detailQuery.isError) {
    drawerContent = <ErrorState message="트렌드 정보를 불러오지 못했습니다." onRetry={() => detailQuery.refetch()} />;
  } else if (detailQuery.isLoading) {
    drawerContent = <Skeleton count={5} />;
  } else if (!detailQuery.data) {
    drawerContent = <EmptyState />;
  } else {
    const trend = detailQuery.data;
    drawerContent = (
      <>
        <div className="detail-label"><span>{trend.category}{trend.tag ? ` / ${trend.tag}` : ''}</span></div>
        <div className="detail-title-row"><h2 className="detail-title">{trend.keyword}</h2><Link className="saved-page-link" to="/saved-trends">저장한 트렌드</Link></div>
        <p className="detail-sub">{trend.description ?? '트렌드 설명이 준비 중입니다.'}</p>
        <p className="detail-period">최근 {periodLabels[period] ?? period} 기준</p>
        <div className="detail-stats">
          <div><span>언급량 · 최근 {periodLabels[period] ?? period}</span><strong>{trend.mentionCount.toLocaleString()}<small>건</small></strong></div>
          <div><span>이전 기간 대비</span><strong className="accent">+{trend.growthRate}%</strong></div>
        </div>
        <section className="detail-chart-section">
          <div className="detail-section-heading"><h3>관심의 움직임</h3><span>최근 {periodLabels[period] ?? period} · 상대 언급 지수</span></div>
          <div className="detail-chart" role="img" aria-label={`${trend.keyword} 언급 지수`}>
            {exampleBars.map((value, index) => <div className="detail-bar-track" key={index}><span style={{ height: `${value}%` }}><b>{value}</b></span></div>)}
          </div>
          <div className="chart-axis"><span>구간 시작</span><span>구간 종료</span></div>
        </section>
        <section className="detail-summary">
          <p className="eyebrow">↗ CONTEXT, NOT JUST NUMBERS</p>
          <h3>왜 눈여겨볼까요?</h3>
          {analysisQuery.isLoading && <Skeleton count={2} />}
          {analysisQuery.isError && <ErrorState onRetry={() => analysisQuery.refetch()} />}
          {analysisQuery.data && <p><strong>{trend.keyword}</strong> — {analysisQuery.data.description}</p>}
        </section>
        <section className="detail-related">
          <h3>함께 살펴볼 키워드</h3>
          {keywordsQuery.isLoading && <Skeleton count={2} />}
          {keywordsQuery.isError && <ErrorState onRetry={() => keywordsQuery.refetch()} />}
          {keywordsQuery.data?.length === 0 && <EmptyState />}
          {keywordsQuery.data && keywordsQuery.data.length > 0 && <div className="keyword-list">{keywordsQuery.data.map((keyword) => <span className="keyword-chip" key={keyword.keywordId ?? keyword.keyword}>{keyword.keyword}</span>)}</div>}
        </section>
        <section className="evidence-section">
          <div className="detail-section-heading"><h3>트렌드의 근거</h3><span>관련 콘텐츠</span></div>
          {contentsQuery.isLoading && <Skeleton count={2} />}
          {contentsQuery.isError && <ErrorState onRetry={() => contentsQuery.refetch()} />}
          {contentsQuery.data?.length === 0 && <EmptyState />}
          {contentsQuery.data && contentsQuery.data.length > 0 && <ul>{contentsQuery.data.map((content) => <li key={content.contentId}><a href={content.url}><strong>{content.title}</strong><span>{content.source ?? '출처 미정'} · {content.publishedAt ?? '게시일 미정'}</span></a></li>)}</ul>}
        </section>
      </>
    );
  }

  return (
    <>
      <div className="drawer-background" aria-hidden="true"><HomePage /></div>
      <div className={`modal-backdrop${isClosing ? ' is-closing' : ''}`} onClick={(event) => { if (event.target === event.currentTarget) closeDrawer(); }}>
        <aside ref={drawerRef} className={`detail-drawer${isClosing ? ' is-closing' : ''}`} role="dialog" aria-modal="true" aria-label="트렌드 상세" tabIndex={-1}>
          <div className="modal-top"><button ref={closeButtonRef} type="button" className="close-button" onClick={closeDrawer} aria-label="상세 패널 닫기">×</button></div>
          <div className="detail-drawer-content">{drawerContent}</div>
        </aside>
      </div>
    </>
  );
}
