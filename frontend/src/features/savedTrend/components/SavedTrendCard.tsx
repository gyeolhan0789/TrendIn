import { Link } from 'react-router-dom';
import { Sparkline } from '../../trend/components/Sparkline';
import { TREND_DRAG_TYPE } from '../dragTypes';
import type { SavedTrend } from '../types/savedTrend';

interface SavedTrendCardProps {
  trend: SavedTrend;
  dragging: boolean;
  deleting: boolean;
  onDragStart: (trendId: string) => void;
  onDragEnd: () => void;
  onDelete: (trendId: string) => void;
}

const RISING_BADGE_THRESHOLD = 200;

/** 순위 변동 표기. change가 없으면 표시할 게 없습니다. */
function formatRankMove(trend: SavedTrend) {
  if (trend.change === 'NEW') return '신규 진입';
  if (typeof trend.change !== 'number' || trend.change === 0) return '';
  return trend.change > 0 ? `▲ ${trend.change}` : `▼ ${Math.abs(trend.change)}`;
}

function deltaTone(trend: SavedTrend) {
  if (trend.change === 'NEW') return 'is-new';
  if (trend.growthRate < 0) return 'is-falling';
  if (trend.growthRate === 0) return 'is-flat';
  return 'is-rising';
}

export function SavedTrendCard({ trend, dragging, deleting, onDragStart, onDragEnd, onDelete }: SavedTrendCardProps) {
  const rankMove = formatRankMove(trend);
  const isSurging = trend.growthRate >= RISING_BADGE_THRESHOLD;
  const className = [
    'saved-card',
    dragging ? 'is-dragging' : '',
    isSurging ? 'is-surging' : '',
  ].filter(Boolean).join(' ');

  return (
    <div
      className={className}
      draggable
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData(TREND_DRAG_TYPE, trend.trendId);
        onDragStart(trend.trendId);
      }}
      onDragEnd={onDragEnd}
    >
      {(isSurging || trend.change === 'NEW') && (
        <div className="saved-card-badges">
          {isSurging && <span className="saved-badge saved-badge--surge">급등</span>}
          {trend.change === 'NEW' && <span className="saved-badge saved-badge--new">NEW</span>}
        </div>
      )}

      <div className="saved-card-head">
        <Link className="saved-card-title" to={{ pathname: `/trends/${trend.trendId}`, search: '?from=saved' }} draggable={false}>{trend.keyword}</Link>
        {/* 이 페이지의 카드는 모두 담긴 상태라 북마크를 채워진 채로 항상 보여줍니다. */}
        <button type="button" className="saved-card-remove" title="담기 취소" aria-label={`${trend.keyword} 담기 취소`} aria-pressed="true" disabled={deleting} onClick={() => onDelete(trend.trendId)}>
          {deleting
            ? <span className="spinner spinner--small" aria-hidden="true" />
            : <svg viewBox="0 0 13 16" width="12" height="15" fill="currentColor" stroke="currentColor" strokeWidth="1.3" aria-hidden="true"><path d="M1.5 1.5h10v13l-5-3.6-5 3.6z" /></svg>}
        </button>
      </div>

      <div className="saved-card-meta">
        <strong className={deltaTone(trend)}>{trend.growthRate > 0 ? '+' : ''}{trend.growthRate}%</strong>
        {rankMove && <span className="saved-card-move">{rankMove}</span>}
        <Sparkline trend={trend} width={54} height={18} color={trend.growthRate < 0 ? '#a4aab3' : '#c2712c'} />
      </div>

      <p className="saved-card-foot">{trend.category}{trend.tag ? ` · ${trend.tag}` : ''} · {trend.mentionCount.toLocaleString()}건</p>
    </div>
  );
}
