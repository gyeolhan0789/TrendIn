import { useEffect, useRef, useState } from 'react';
import { UNSORTED_BOARD_ID } from '../api/savedBoardStorage';
import type { SavedBoardView } from '../types/savedTrend';
import { SavedTrendCard } from './SavedTrendCard';

interface SavedBoardPanelProps {
  board: SavedBoardView;
  draggingTrendId?: string;
  deletingTrendId?: string;
  onDragStart: (trendId: string) => void;
  onDragEnd: () => void;
  onDelete: (trendId: string) => void;
  onRename: (boardId: string, name: string) => void;
  onRemove: (boardId: string) => void;
}

export function SavedBoardPanel(props: SavedBoardPanelProps) {
  const { board, draggingTrendId, deletingTrendId } = props;
  const isUnsorted = board.boardId === UNSORTED_BOARD_ID;
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const renameInput = useRef<HTMLInputElement>(null);

  // 다른 보드로 넘어가면 열려 있던 메뉴와 이름 입력을 닫습니다.
  useEffect(() => {
    setMenuOpen(false);
    setRenaming(false);
  }, [board.boardId]);

  useEffect(() => {
    if (renaming) renameInput.current?.select();
  }, [renaming]);

  const commitRename = () => {
    const value = renameInput.current?.value ?? '';
    if (value.trim() && value.trim() !== board.name) props.onRename(board.boardId, value);
    setRenaming(false);
  };

  return (
    <section className="saved-panel" aria-label={`${board.name} 보드`}>
      <header className="saved-panel-head">
        {renaming
          ? <input ref={renameInput} className="saved-panel-rename" defaultValue={board.name} maxLength={24} aria-label="보드 이름" onBlur={commitRename} onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.nativeEvent.isComposing) commitRename();
            if (event.key === 'Escape') setRenaming(false);
          }} />
          : <h2>{board.name}<span>{board.trends.length}</span></h2>}
        {!isUnsorted && !renaming && (
          <div className="saved-panel-menu">
            <button type="button" aria-expanded={menuOpen} aria-label={`${board.name} 보드 설정`} onClick={() => setMenuOpen((open) => !open)}>⋯</button>
            {menuOpen && (
              <div className="saved-panel-popover" onMouseLeave={() => setMenuOpen(false)}>
                <button type="button" onClick={() => { setMenuOpen(false); setRenaming(true); }}>이름 변경</button>
                <button type="button" className="is-danger" onClick={() => { setMenuOpen(false); props.onRemove(board.boardId); }}>보드 삭제</button>
              </div>
            )}
          </div>
        )}
      </header>

      {board.trends.length === 0
        ? <p className="saved-panel-empty">{isUnsorted ? '분류하지 않은 키워드가 여기에 모입니다.' : '카드를 왼쪽 보드 목록으로 끌어다 옮길 수 있습니다.'}</p>
        : (
          <div className="saved-panel-grid">
            {board.trends.map((trend) => (
              <SavedTrendCard
                key={trend.trendId}
                trend={trend}
                dragging={draggingTrendId === trend.trendId}
                deleting={deletingTrendId === trend.trendId}
                onDragStart={props.onDragStart}
                onDragEnd={props.onDragEnd}
                onDelete={props.onDelete}
              />
            ))}
          </div>
        )}
    </section>
  );
}
