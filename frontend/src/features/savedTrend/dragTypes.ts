/*
 * 보드 목록은 두 종류의 드롭을 받습니다: 카드를 끌어와 분류하는 것과, 보드끼리 순서를 바꾸는 것.
 * dataTransfer의 타입으로 구분해야 서로를 잘못 처리하지 않습니다.
 */
export const TREND_DRAG_TYPE = 'application/x-trendin-trend';
export const BOARD_DRAG_TYPE = 'application/x-trendin-board';

export function isDragOfType(dataTransfer: DataTransfer, type: string) {
  // types는 DOMStringList처럼 동작해 includes가 없는 브라우저도 있어 배열로 감싸 확인합니다.
  return Array.from(dataTransfer.types).includes(type);
}
