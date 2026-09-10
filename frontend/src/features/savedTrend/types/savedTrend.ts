import type { Trend } from '../../trend/types/trend';

export interface SavedTrend extends Trend {
  savedAt?: string;
}

/** 사용자가 저장한 키워드를 묶어두는 보드. 백엔드가 없어 기기에만 보관합니다. */
export interface SavedBoard {
  boardId: string;
  name: string;
  /** YYYY.MM.DD. 담기 패널에 만든 날짜로 표시합니다. */
  createdAt: string;
}

export interface SavedBoardState {
  boards: SavedBoard[];
  /** trendId -> boardId. 값이 없는 키워드는 미분류 열에 남습니다. */
  assignments: Record<string, string>;
}

/** 화면에 그릴 보드 한 개. 미분류를 포함하며 소속 키워드를 함께 담습니다. */
export interface SavedBoardView {
  boardId: string;
  name: string;
  trends: SavedTrend[];
}
