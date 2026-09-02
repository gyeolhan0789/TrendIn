import { Link, useLocation } from 'react-router-dom';
import type { Trend } from '../types/trend';

interface TrendCardProps {
  trend: Trend;
  rank?: number;
  variant?: 'default' | 'compact';
  showMetaArrow?: boolean;
}

export function TrendCard({ trend, rank = 1, variant = 'default', showMetaArrow = true }: TrendCardProps) {
  const location = useLocation();
  const detailUrl = { pathname: `/trends/${trend.trendId}`, search: location.search };
  const rankChange = getRankChange(trend.change);

  if (variant === 'compact') {
    return (
      <Link className="compact-trend-item" to={detailUrl}>
        <span className="compact-trend-item__rank">{String(rank).padStart(2, '0')}</span>
        <span className="compact-trend-item__copy">
          <span className="compact-trend-item__kicker">{trend.category}{trend.tag ? ` · ${trend.tag}` : ''}</span>
          <strong className="compact-trend-item__title">{trend.keyword}</strong>
          <span className="compact-trend-item__description">{trend.description ?? '지금 주목받고 있는 새로운 흐름'}</span>
        </span>
        <span className="compact-trend-item__meta">{trend.kind === 'new' ? '새로운 등장' : `+${trend.growthRate}%`}{showMetaArrow && <span aria-hidden="true">↗</span>}</span>
      </Link>
    );
  }

  return (
    <Link className={`trend-card card-${rank}`} to={detailUrl}>
      <span className="card-topline">
        <span className="card-rank">{String(rank).padStart(2, '0')}</span>
        <span className={`rank-change ${rankChange.className}`} aria-label={rankChange.ariaLabel}>{rankChange.label}</span>
      </span>
      <span className="card-copy">
        <span className="card-tag"><span className="spotlight-dot" />{trend.category}{rank === 1 ? ' / IN THE SPOTLIGHT' : ''}</span>
        <strong className="card-title">{trend.keyword}</strong>
        <span className="card-description">지금 주목받고 있는 {trend.category}의 흐름</span>
      </span>
      {rank === 1 && <span className="card-context">오늘의 대화가 모이는 곳.<br />지금 가장 주목받는 흐름을 만나보세요.</span>}
      <span className="card-metrics">
        <span><span className="metric-label">언급량</span><strong>{trend.mentionCount.toLocaleString()}<small>건</small></strong></span>
        <span><span className="metric-label">관심도 증가</span><strong className="card-growth">+{trend.growthRate}<small>%</small></strong></span>
      </span>
    </Link>
  );
}

function getRankChange(value: Trend['change']) {
  if (value === 'NEW') return { label: 'NEW', className: 'new', ariaLabel: '순위 신규 진입' };
  if (!value) return { label: '—', className: '', ariaLabel: '순위 변동 없음' };
  return {
    label: `${value > 0 ? '▲' : '▼'} ${Math.abs(value)}`,
    className: value < 0 ? 'down' : '',
    ariaLabel: `${Math.abs(value)}계단 ${value > 0 ? '상승' : '하락'}`,
  };
}
