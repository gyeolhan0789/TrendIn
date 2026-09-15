import { Link } from 'react-router-dom';
import { BookmarkButton } from './BookmarkButton';
import { TagChip } from '../../trend/components/TagChip';
import { formatCount, formatGrowth } from '../../trend/trendFormat';
import type { SavedTrend } from '../types/savedTrend';

const SURGE_THRESHOLD = 100;
const RISE_THRESHOLD = 50;

/** 시안은 오름폭에 따라 숫자 색을 달리 합니다. 증가율이 비어 오면 고를 근거가 없어 회색으로 둡니다. */
function growthTone(growthRate: number | null) {
  if (growthRate === null) return 'is-blank';
  if (growthRate < 0) return 'is-falling';
  if (growthRate >= SURGE_THRESHOLD) return 'is-surging';
  if (growthRate >= RISE_THRESHOLD) return 'is-rising';
  return 'is-flat';
}

/** 앞의 YYYY-MM-DD 만 떼어 씁니다. Date 로 읽으면 시간대에 따라 하루가 밀릴 수 있습니다. */
function formatSavedDate(savedAt: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(savedAt);
  return match ? `${match[1]}.${match[2]}.${match[3]}` : savedAt;
}

export function SavedTrendCard({ trend }: { trend: SavedTrend }) {
  return (
    <article className="saved-card">
      <div className="saved-card-head">
        <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="saved-card-bookmark" />
        <Link className="saved-card-title" to={{ pathname: `/trends/${trend.trendId}`, search: '?from=saved' }}>{trend.keyword}</Link>
        <TagChip label={trend.domain.name} />
      </div>

      <div className="saved-card-metrics">
        <strong className={growthTone(trend.growthRate)}>{formatGrowth(trend.growthRate)}</strong>
        <span>{trend.mentionCount === null ? '언급량 집계 전' : `언급량 ${formatCount(trend.mentionCount)}`}</span>
      </div>

      {/* 설명이 없는 트렌드가 섞여도 카드 높이가 들쭉날쭉하지 않도록 저장일 줄을 바닥에 붙입니다. */}
      {trend.description && <p className="saved-card-summary">{trend.description}</p>}

      <div className="saved-card-foot">저장일 {formatSavedDate(trend.savedAt)}</div>
    </article>
  );
}
