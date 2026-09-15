import { Link } from 'react-router-dom';
import { BookmarkButton } from './BookmarkButton';
import type { SavedTrend } from '../types/savedTrend';

interface SavedTrendCardProps {
  trend: SavedTrend;
}

const SURGE_THRESHOLD = 100;

function formatGrowthRate(growthRate: number | null) {
  if (growthRate === null) return '—';
  return `${growthRate > 0 ? '+' : ''}${growthRate}%`;
}

function growthTone(growthRate: number | null) {
  if (growthRate === null) return '';
  if (growthRate < 0) return 'is-falling';
  if (growthRate === 0) return 'is-flat';
  return 'is-rising';
}

export function SavedTrendCard({ trend }: SavedTrendCardProps) {
  const surging = trend.growthRate !== null && trend.growthRate >= SURGE_THRESHOLD;
  const isNew = trend.trendTypes.includes('NEW');

  return (
    <div className={`saved-card${surging ? ' is-surging' : ''}`}>
      {(surging || isNew) && (
        <div className="saved-card-badges">
          {surging && <span className="saved-badge saved-badge--surge">급등</span>}
          {isNew && <span className="saved-badge saved-badge--new">NEW</span>}
        </div>
      )}

      <div className="saved-card-head">
        <Link className="saved-card-title" to={{ pathname: `/trends/${trend.trendId}`, search: '?from=saved' }}>{trend.keyword}</Link>
        <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="saved-card-remove" />
      </div>

      <div className="saved-card-meta">
        <strong className={growthTone(trend.growthRate)}>{formatGrowthRate(trend.growthRate)}</strong>
      </div>

      {/* 설명은 한 문장이라 증감률 옆에 두면 카드를 넘칩니다. 줄을 따로 쓰고 두 줄에서 자릅니다. */}
      {trend.description && <p className="saved-card-summary">{trend.description}</p>}

      <p className="saved-card-foot">
        {trend.domain.name}
        {trend.mentionCount !== null && ` · ${trend.mentionCount.toLocaleString()}건`}
      </p>
    </div>
  );
}
