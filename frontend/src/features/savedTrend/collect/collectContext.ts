import { createContext, useContext } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import type { Trend } from '../../trend/types/trend';

/** 담기 패널의 "새 영역" 칸을 가리키는 가상 드롭 대상. */
export const NEW_ZONE_ID = '__new';

export interface CollectZone {
  boardId: string;
  name: string;
  createdAt: string;
  count: number;
}

export interface CollectContextValue {
  zones: CollectZone[];
  savedCount: number;
  isSaved: (trendId: string) => boolean;
  boardNameOf: (trendId: string) => string;
  /** 북마크 아이콘: 담기 ↔ 담기 취소 토글. */
  toggleSave: (trend: Trend) => void;
  /** 키워드를 잡아 끄는 동작을 시작합니다. */
  startDrag: (trend: Trend, event: ReactPointerEvent) => void;
  /** 드래그 직후의 클릭인지. 링크 이동을 막는 데 씁니다. */
  consumeDragClick: () => boolean;
  draggingTrendId?: string;
  /** 커서를 따라다니는 라벨에 쓸 키워드. */
  dragLabel?: string;
  dragMoved: boolean;
  /** 드래그를 끝냈지만 아직 분류되지 않은 키워드. */
  pendingKeyword?: string;
  ghost: { x: number; y: number };
  dropTarget?: string;
  trayOpen: boolean;
  openTray: () => void;
  closeTray: () => void;
  toggleTray: () => void;
  pulse: boolean;
  newZoneEditing: boolean;
  openNewZone: () => void;
  cancelNewZone: () => void;
  fileIntoBoard: (boardId: string) => void;
  createZone: (name: string) => void;
}

export const CollectContext = createContext<CollectContextValue | undefined>(undefined);

export function useCollect() {
  const value = useContext(CollectContext);
  if (!value) throw new Error('useCollect must be used inside CollectProvider.');
  return value;
}

