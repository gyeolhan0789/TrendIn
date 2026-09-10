import type { PointerEvent as ReactPointerEvent, MouseEvent as ReactMouseEvent } from 'react';
import type { Trend } from '../../trend/types/trend';
import { useCollect } from './collectContext';

/**
 * 키워드를 집어 끌 수 있게 만드는 props 묶음.
 * 움직이지 않고 뗀 클릭은 그대로 통과시켜 상세 페이지로 이동합니다.
 */
export function useCollectHandlers(trend: Trend) {
  const { startDrag, consumeDragClick, draggingTrendId } = useCollect();

  return {
    draggable: false,
    'data-collect-grabbed': draggingTrendId === trend.trendId ? '' : undefined,
    onPointerDown: (event: ReactPointerEvent) => startDrag(trend, event),
    onClick: (event: ReactMouseEvent) => {
      if (consumeDragClick()) event.preventDefault();
    },
  };
}
