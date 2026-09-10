import { useCallback, useSyncExternalStore } from 'react';
import {
  UNSORTED_BOARD_ID,
  formatBoardDate,
  getSavedBoardState,
  setSavedBoardState,
  subscribeSavedBoardState,
} from '../api/savedBoardStorage';
import type { SavedBoardState } from '../types/savedTrend';

const newBoardNamePattern = /^새 보드 (\d+)$/;

function nextBoardName(state: SavedBoardState) {
  const used = state.boards.map((board) => Number(newBoardNamePattern.exec(board.name)?.[1] ?? 0));
  return `새 보드 ${Math.max(0, ...used) + 1}`;
}

export function useSavedBoards() {
  const state = useSyncExternalStore(subscribeSavedBoardState, getSavedBoardState);

  const update = useCallback((next: (current: SavedBoardState) => SavedBoardState) => {
    const current = getSavedBoardState();
    const value = next(current);
    if (value !== current) setSavedBoardState(value);
  }, []);

  const addBoard = useCallback((name?: string) => {
    const current = getSavedBoardState();
    const board = {
      boardId: `board-${Date.now().toString(36)}`,
      name: name?.trim() || nextBoardName(current),
      createdAt: formatBoardDate(new Date()),
    };
    update((state) => ({ ...state, boards: [...state.boards, board] }));
    return board;
  }, [update]);

  const renameBoard = useCallback((boardId: string, name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    update((current) => ({
      ...current,
      boards: current.boards.map((board) => (board.boardId === boardId ? { ...board, name: trimmed } : board)),
    }));
  }, [update]);

  /** 보드만 지우고 안에 있던 키워드는 미분류로 되돌립니다. */
  const removeBoard = useCallback((boardId: string) => {
    update((current) => ({
      boards: current.boards.filter((board) => board.boardId !== boardId),
      assignments: Object.fromEntries(Object.entries(current.assignments).filter(([, id]) => id !== boardId)),
    }));
  }, [update]);

  /** 끌어온 보드를 대상 보드의 앞(또는 뒤)에 끼워 넣습니다. 미분류는 목록에 없어 영향받지 않습니다. */
  const moveBoard = useCallback((boardId: string, targetBoardId: string, after: boolean) => {
    if (boardId === targetBoardId) return;
    update((current) => {
      const from = current.boards.findIndex((board) => board.boardId === boardId);
      if (from < 0) return current;
      const next = [...current.boards];
      const [moved] = next.splice(from, 1);
      const targetIndex = next.findIndex((board) => board.boardId === targetBoardId);
      const to = targetIndex < 0 ? next.length : targetIndex + (after ? 1 : 0);
      next.splice(to, 0, moved);
      return { ...current, boards: next };
    });
  }, [update]);

  const assignTrends = useCallback((trendIds: string[], boardId: string) => {
    update((current) => {
      const assignments = { ...current.assignments };
      trendIds.forEach((trendId) => {
        if (boardId === UNSORTED_BOARD_ID) delete assignments[trendId];
        else assignments[trendId] = boardId;
      });
      return { ...current, assignments };
    });
  }, [update]);

  /** 저장 목록에서 사라진 키워드의 분류 정보를 정리합니다. */
  const pruneAssignments = useCallback((trendIds: string[]) => {
    update((current) => {
      const valid = new Set(trendIds);
      const entries = Object.entries(current.assignments).filter(([trendId]) => valid.has(trendId));
      if (entries.length === Object.keys(current.assignments).length) return current;
      return { ...current, assignments: Object.fromEntries(entries) };
    });
  }, [update]);

  return { boards: state.boards, assignments: state.assignments, addBoard, renameBoard, removeBoard, moveBoard, assignTrends, pruneAssignments };
}
