import { useState } from 'react';
import type { DragEvent } from 'react';
import { UNSORTED_BOARD_ID } from '../api/savedBoardStorage';
import { BOARD_DRAG_TYPE, TREND_DRAG_TYPE, isDragOfType } from '../dragTypes';
import type { SavedBoardView } from '../types/savedTrend';

interface SavedBoardNavProps {
  boards: SavedBoardView[];
  selectedBoardId: string;
  cardDropTargetId?: string;
  draggingCard: boolean;
  onSelect: (boardId: string) => void;
  onCardDragOver: (boardId: string) => void;
  onCardDragLeave: (boardId: string) => void;
  onCardDrop: (boardId: string) => void;
  onReorder: (boardId: string, targetBoardId: string, after: boolean) => void;
  onAdd: () => void;
}

/** 커서가 항목의 아래 절반에 있으면 그 뒤에 끼워 넣습니다. */
function isAfterMidpoint(event: DragEvent<HTMLElement>) {
  const box = event.currentTarget.getBoundingClientRect();
  return event.clientY > box.top + box.height / 2;
}

export function SavedBoardNav(props: SavedBoardNavProps) {
  const { boards, selectedBoardId, cardDropTargetId, draggingCard } = props;
  const [draggingBoardId, setDraggingBoardId] = useState<string>();
  const [insertAt, setInsertAt] = useState<{ boardId: string; after: boolean }>();

  const endBoardDrag = () => {
    setDraggingBoardId(undefined);
    setInsertAt(undefined);
  };

  return (
    <nav className={`saved-nav${draggingCard ? ' is-receiving' : ''}`} aria-label="보드 목록">
      {boards.map((board) => {
        const isUnsorted = board.boardId === UNSORTED_BOARD_ID;
        const insert = insertAt?.boardId === board.boardId ? insertAt : undefined;
        const className = [
          'saved-nav-item',
          board.boardId === selectedBoardId ? 'is-selected' : '',
          isUnsorted ? 'saved-nav-item--unsorted' : '',
          cardDropTargetId === board.boardId ? 'is-drop-target' : '',
          board.boardId === draggingBoardId ? 'is-dragging' : '',
          insert ? (insert.after ? 'is-insert-after' : 'is-insert-before') : '',
        ].filter(Boolean).join(' ');

        return (
          <button
            type="button"
            key={board.boardId}
            className={className}
            aria-current={board.boardId === selectedBoardId}
            // 미분류는 항상 첫 자리에 고정이라 끌 수 없습니다.
            draggable={!isUnsorted}
            onClick={() => props.onSelect(board.boardId)}
            onDragStart={(event) => {
              event.dataTransfer.effectAllowed = 'move';
              event.dataTransfer.setData(BOARD_DRAG_TYPE, board.boardId);
              setDraggingBoardId(board.boardId);
            }}
            onDragEnd={endBoardDrag}
            onDragOver={(event) => {
              if (isDragOfType(event.dataTransfer, TREND_DRAG_TYPE)) {
                event.preventDefault();
                props.onCardDragOver(board.boardId);
                return;
              }
              // 미분류 위로는 순서를 옮길 수 없습니다.
              if (!isDragOfType(event.dataTransfer, BOARD_DRAG_TYPE) || isUnsorted) return;
              event.preventDefault();
              setInsertAt({ boardId: board.boardId, after: isAfterMidpoint(event) });
            }}
            onDragLeave={() => {
              props.onCardDragLeave(board.boardId);
              setInsertAt((current) => (current?.boardId === board.boardId ? undefined : current));
            }}
            onDrop={(event) => {
              event.preventDefault();
              if (isDragOfType(event.dataTransfer, TREND_DRAG_TYPE)) {
                props.onCardDrop(board.boardId);
                return;
              }
              const movedId = event.dataTransfer.getData(BOARD_DRAG_TYPE);
              if (movedId && !isUnsorted) props.onReorder(movedId, board.boardId, isAfterMidpoint(event));
              endBoardDrag();
            }}
          >
            <span>{board.name}</span>
            <small>{board.trends.length}</small>
          </button>
        );
      })}
      <button type="button" className="saved-nav-add" onClick={props.onAdd}>+ 새 보드</button>
    </nav>
  );
}
