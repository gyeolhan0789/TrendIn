import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { PageContainer } from '../../components/layout/PageContainer';
import { showToast } from '../../components/common/toast';
import { UNSORTED_BOARD_ID, UNSORTED_BOARD_NAME } from '../../features/savedTrend/api/savedBoardStorage';
import { SavedBoardNav } from '../../features/savedTrend/components/SavedBoardNav';
import { SavedBoardPanel } from '../../features/savedTrend/components/SavedBoardPanel';
import { useDeleteSavedTrend } from '../../features/savedTrend/hooks/useDeleteSavedTrend';
import { useSavedBoards } from '../../features/savedTrend/hooks/useSavedBoards';
import { useSavedTrends } from '../../features/savedTrend/hooks/useSavedTrends';
import type { SavedBoardView, SavedTrend } from '../../features/savedTrend/types/savedTrend';

function parseSavedAt(trend: SavedTrend) {
  const time = trend.savedAt ? Date.parse(trend.savedAt) : Number.NaN;
  return Number.isNaN(time) ? 0 : time;
}

interface SavedOverview {
  total: number;
  rising: SavedTrend[];
  fresh: SavedTrend[];
  falling: SavedTrend[];
}

function summarise(trends: SavedTrend[]): SavedOverview {
  return {
    total: trends.length,
    rising: [...trends].filter((trend) => trend.growthRate > 0).sort((a, b) => b.growthRate - a.growthRate),
    fresh: trends.filter((trend) => trend.change === 'NEW'),
    falling: [...trends].filter((trend) => trend.growthRate < 0).sort((a, b) => a.growthRate - b.growthRate),
  };
}

function SavedOverviewCards({ overview }: { overview: SavedOverview }) {
  const leader = overview.rising[0];
  const newest = overview.fresh[0];
  const weakest = overview.falling[0];

  return (
    <div className="saved-overview" aria-label="저장한 트렌드 요약">
      <div className="saved-overview-card">
        <span>급등 중</span>
        <strong className="is-rising">{overview.rising.length}<small>/ {overview.total}</small></strong>
        <p>{leader ? `${leader.keyword} +${leader.growthRate}% 선두` : '—'}</p>
      </div>
      <div className="saved-overview-card">
        <span>신규 진입</span>
        <strong className="is-new">{overview.fresh.length}<small>/ {overview.total}</small></strong>
        <p>{newest ? `${newest.keyword} 처음 등장` : '—'}</p>
      </div>
      <div className="saved-overview-card">
        <span>주의 · 하락 전환</span>
        <strong className="is-falling">{overview.falling.length}<small>/ {overview.total}</small></strong>
        <p>{weakest ? `${weakest.keyword} ${weakest.growthRate}%` : '없음'}</p>
      </div>
    </div>
  );
}

function SavedEmpty() {
  return (
    <div className="saved-empty">
      <p>저장한 트렌드는 순위 변동과 언급량 추이를 계속 따라갑니다.</p>
      <h2>대시보드에서 마음에 드는 키워드의 북마크를 눌러보세요.</h2>
      <Link className="saved-empty-action" to="/dashboard">오늘의 흐름 살펴보기<span aria-hidden="true">→</span></Link>
    </div>
  );
}

export function SavedTrendPage() {
  const savedTrendsQuery = useSavedTrends();
  const deleteMutation = useDeleteSavedTrend();
  const { boards, assignments, addBoard, renameBoard, removeBoard, moveBoard, assignTrends, pruneAssignments } = useSavedBoards();

  const [selectedBoardId, setSelectedBoardId] = useState(UNSORTED_BOARD_ID);
  const [draggingTrendId, setDraggingTrendId] = useState<string>();
  const [cardDropTargetId, setCardDropTargetId] = useState<string>();

  // 아래 이펙트가 trends를 의존하므로, 빈 배열도 매 렌더 같은 참조로 유지해야 합니다.
  const trends = useMemo(() => savedTrendsQuery.data ?? [], [savedTrendsQuery.data]);
  const isReady = !savedTrendsQuery.isLoading && !savedTrendsQuery.isError;

  useEffect(() => {
    if (savedTrendsQuery.isSuccess) pruneAssignments(trends.map((trend) => trend.trendId));
  }, [pruneAssignments, savedTrendsQuery.isSuccess, trends]);

  const boardViews = useMemo<SavedBoardView[]>(() => {
    // 최근 저장한 키워드가 앞에 오도록 정렬합니다.
    const ordered = [...trends].reverse().sort((a, b) => parseSavedAt(b) - parseSavedAt(a));
    const byBoard = new Map<string, SavedTrend[]>(boards.map((board) => [board.boardId, []]));
    const unsorted: SavedTrend[] = [];
    ordered.forEach((trend) => {
      const bucket = byBoard.get(assignments[trend.trendId] ?? '');
      if (bucket) bucket.push(trend);
      else unsorted.push(trend);
    });
    return [
      { boardId: UNSORTED_BOARD_ID, name: UNSORTED_BOARD_NAME, trends: unsorted },
      ...boards.map((board) => ({ ...board, trends: byBoard.get(board.boardId) ?? [] })),
    ];
  }, [assignments, boards, trends]);

  // 보고 있던 보드가 삭제되면 미분류로 돌아갑니다.
  const selectedBoard = boardViews.find((board) => board.boardId === selectedBoardId) ?? boardViews[0];
  useEffect(() => {
    if (selectedBoard.boardId !== selectedBoardId) setSelectedBoardId(selectedBoard.boardId);
  }, [selectedBoard.boardId, selectedBoardId]);

  const overview = useMemo(() => summarise(trends), [trends]);

  const dropCardOnBoard = (boardId: string) => {
    const trendId = draggingTrendId;
    setDraggingTrendId(undefined);
    setCardDropTargetId(undefined);
    if (!trendId || (assignments[trendId] ?? UNSORTED_BOARD_ID) === boardId) return;
    const target = boardViews.find((board) => board.boardId === boardId);
    assignTrends([trendId], boardId);
    showToast({ message: `${target?.name ?? '보드'}(으)로 옮겼습니다.`, type: 'success' });
  };

  const createBoard = () => {
    const board = addBoard();
    setSelectedBoardId(board.boardId);
    showToast({ message: `${board.name}을(를) 만들었습니다.`, type: 'success' });
  };

  const deleteBoard = (boardId: string) => {
    const target = boardViews.find((board) => board.boardId === boardId);
    removeBoard(boardId);
    setSelectedBoardId(UNSORTED_BOARD_ID);
    showToast({ message: `${target?.name ?? '보드'}을(를) 삭제했습니다. 키워드는 미분류로 옮겼습니다.`, type: 'success' });
  };

  return (
    <PageContainer>
      <div className="saved-page">
        <div className="saved-titlebar">
          <h1>저장한 트렌드</h1>
          <p>{trends.length > 0
            ? `키워드 ${trends.length}개 · 보드 ${boards.length}개 · 카드는 보드로, 보드는 목록 안에서 끌어 옮길 수 있습니다`
            : '저장한 흐름을 보드로 모아 언급량과 순위 변화를 이어서 봅니다'}</p>
        </div>

        {savedTrendsQuery.isLoading && <div className="saved-loading" aria-label="불러오는 중"><span /><span /><span /></div>}
        {savedTrendsQuery.isError && <ErrorState message="저장한 트렌드를 불러오지 못했습니다." onRetry={() => savedTrendsQuery.refetch()} />}

        {isReady && trends.length === 0 && <SavedEmpty />}
        {isReady && trends.length > 0 && (
          <>
            <SavedOverviewCards overview={overview} />
            <div className="saved-workspace">
              <SavedBoardNav
                boards={boardViews}
                selectedBoardId={selectedBoard.boardId}
                cardDropTargetId={cardDropTargetId}
                draggingCard={Boolean(draggingTrendId)}
                onSelect={setSelectedBoardId}
                onCardDragOver={setCardDropTargetId}
                onCardDragLeave={(boardId) => setCardDropTargetId((current) => (current === boardId ? undefined : current))}
                onCardDrop={dropCardOnBoard}
                onReorder={moveBoard}
                onAdd={createBoard}
              />
              <SavedBoardPanel
                board={selectedBoard}
                draggingTrendId={draggingTrendId}
                deletingTrendId={deleteMutation.isPending ? deleteMutation.variables : undefined}
                onDragStart={setDraggingTrendId}
                onDragEnd={() => { setDraggingTrendId(undefined); setCardDropTargetId(undefined); }}
                onDelete={(trendId) => deleteMutation.mutate(trendId)}
                onRename={renameBoard}
                onRemove={deleteBoard}
              />
            </div>
          </>
        )}
      </div>
    </PageContainer>
  );
}
