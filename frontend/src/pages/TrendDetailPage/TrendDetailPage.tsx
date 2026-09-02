import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { HomePage } from '../HomePage/HomePage';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { Skeleton } from '../../components/common/Skeleton';
import { useTrendDetail } from '../../features/trend/hooks/useTrendDetail';

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
        <div className="detail-title-row"><h2 className="detail-title">{trend.keyword}</h2></div>
        <p className="detail-sub">{trend.description ?? '트렌드 설명이 준비 중입니다.'}</p>
        <p className="detail-period">최근 {periodLabels[period] ?? period} 기준</p>
        <div className="detail-stats">
          <div><span>언급량 · 최근 {periodLabels[period] ?? period}</span><strong>{trend.mentionCount.toLocaleString()}<small>건</small></strong></div>
          <div><span>이전 기간 대비</span><strong className="accent">+{trend.growthRate}%</strong></div>
        </div>
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
