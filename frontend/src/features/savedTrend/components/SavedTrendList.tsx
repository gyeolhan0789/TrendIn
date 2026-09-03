import type { SavedTrend } from '../types/savedTrend';
import { Button } from '../../../components/common/Button';
import { TrendCard } from '../../trend/components/TrendCard';

interface SavedTrendListProps {
  trends: SavedTrend[];
  deletingTrendId?: string;
  onDelete: (trendId: string) => void;
}

export function SavedTrendList({ trends, deletingTrendId, onDelete }: SavedTrendListProps) {
  return (
    <div className="saved-trend-list">
      {trends.map((trend) => (
        <div className="saved-trend-item" key={trend.trendId}>
          <TrendCard trend={trend} variant="compact" />
          <Button type="button" isLoading={deletingTrendId === trend.trendId} onClick={() => onDelete(trend.trendId)}>
            삭제
          </Button>
        </div>
      ))}
    </div>
  );
}
