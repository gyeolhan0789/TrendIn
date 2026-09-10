import type { SavedBoard, SavedBoardState } from '../types/savedTrend';

const boardStateKey = 'trendin-saved-boards-v1';

/** 미분류 열은 저장되지 않는 가상 보드입니다. */
export const UNSORTED_BOARD_ID = 'unsorted';
export const UNSORTED_BOARD_NAME = '미분류';

const emptyBoardState: SavedBoardState = { boards: [], assignments: {} };

function parseBoards(value: unknown): SavedBoard[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((board): board is SavedBoard =>
      Boolean(board) && typeof board === 'object'
      && typeof (board as SavedBoard).boardId === 'string'
      && typeof (board as SavedBoard).name === 'string'
      && (board as SavedBoard).boardId !== UNSORTED_BOARD_ID)
    .map((board) => ({ ...board, createdAt: typeof board.createdAt === 'string' ? board.createdAt : '' }));
}

export function formatBoardDate(date: Date) {
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
}

function parseAssignments(value: unknown, boards: SavedBoard[]): Record<string, string> {
  if (!value || typeof value !== 'object') return {};
  const boardIds = new Set(boards.map((board) => board.boardId));
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, boardId]) => typeof boardId === 'string' && boardIds.has(boardId));
  return Object.fromEntries(entries) as Record<string, string>;
}

function readSavedBoardState(): SavedBoardState {
  try {
    const raw = window.localStorage.getItem(boardStateKey);
    if (!raw) return emptyBoardState;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return emptyBoardState;
    const boards = parseBoards((parsed as SavedBoardState).boards);
    return { boards, assignments: parseAssignments((parsed as SavedBoardState).assignments, boards) };
  } catch {
    return emptyBoardState;
  }
}

/*
 * 담기 패널과 저장 페이지가 같은 보드 상태를 봐야 하므로, 훅마다 useState를 두지 않고
 * 모듈 하나에 담아 구독합니다. 훅별로 복사본을 들면 한쪽 쓰기가 다른 쪽에 보이지 않습니다.
 */
let cachedState: SavedBoardState | undefined;
const listeners = new Set<() => void>();

export function getSavedBoardState(): SavedBoardState {
  cachedState ??= readSavedBoardState();
  return cachedState;
}

export function setSavedBoardState(state: SavedBoardState) {
  cachedState = state;
  try {
    window.localStorage.setItem(boardStateKey, JSON.stringify(state));
  } catch {
    // Device-local storage may be unavailable in private browsing.
  }
  listeners.forEach((listener) => listener());
}

export function subscribeSavedBoardState(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
