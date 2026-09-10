import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, PropsWithChildren } from 'react';
import { showToast } from '../../../components/common/toast';
import type { Trend } from '../../trend/types/trend';
import { UNSORTED_BOARD_ID, UNSORTED_BOARD_NAME } from '../api/savedBoardStorage';
import { useDeleteSavedTrend } from '../hooks/useDeleteSavedTrend';
import { useSaveTrend } from '../hooks/useSaveTrend';
import { useSavedBoards } from '../hooks/useSavedBoards';
import { useSavedTrends } from '../hooks/useSavedTrends';
import { CollectContext, NEW_ZONE_ID } from './collectContext';
import type { CollectContextValue, CollectZone } from './collectContext';

/** 이만큼 움직여야 클릭이 아니라 드래그로 봅니다. */
const DRAG_THRESHOLD = 3;

interface DragSession {
  trend: Trend;
  origin: { x: number; y: number };
  moved: boolean;
  target?: string;
  trayWasOpen: boolean;
}

export function CollectProvider({ children }: PropsWithChildren) {
  const savedTrendsQuery = useSavedTrends();
  const { boards, assignments, addBoard, assignTrends } = useSavedBoards();

  const savedTrends = savedTrendsQuery.data ?? [];
  const savedIds = useMemo(() => new Set(savedTrends.map((trend) => trend.trendId)), [savedTrends]);

  const boardNameOf = useCallback((trendId: string) => {
    const boardId = assignments[trendId];
    return boards.find((board) => board.boardId === boardId)?.name ?? UNSORTED_BOARD_NAME;
  }, [assignments, boards]);

  /*
   * 토스트 문구는 mutation이 성공한 뒤에 만들어지는데, 그때는 이미 분류 정보가 바뀌어 있습니다.
   * 그래서 어느 영역에 담았는지/어디서 뺐는지를 요청 시점에 기억해 둡니다.
   */
  const targetBoardName = useRef<Record<string, string>>({});
  const takeBoardName = (trendId: string) => {
    const name = targetBoardName.current[trendId];
    delete targetBoardName.current[trendId];
    return name;
  };

  const saveMutation = useSaveTrend({
    successMessage: (trendId) => {
      const name = takeBoardName(trendId);
      return name ? `${name}에 담았습니다.` : `${UNSORTED_BOARD_NAME}에 담았습니다 · 담기 패널에서 분류하세요.`;
    },
  });
  const deleteMutation = useDeleteSavedTrend({
    successMessage: (trendId) => `${takeBoardName(trendId) ?? UNSORTED_BOARD_NAME}에서 뺐습니다.`,
  });

  /** 포인터를 누르고 있는 동안의 드래그. 커서 라벨과 강조에만 씁니다. */
  const [dragging, setDragging] = useState<Trend>();
  /** 드래그를 끝냈지만 아직 분류되지 않은 키워드. 패널에서 클릭으로 마무리할 수 있습니다. */
  const [pendingTrend, setPendingTrend] = useState<Trend>();
  const [dragMoved, setDragMoved] = useState(false);
  const [ghost, setGhost] = useState({ x: 0, y: 0 });
  const [dropTarget, setDropTarget] = useState<string>();
  const [trayOpen, setTrayOpen] = useState(false);
  const [newZoneEditing, setNewZoneEditing] = useState(false);
  const [pulse, setPulse] = useState(false);

  // 포인터 핸들러는 window에 붙으므로 진행 중인 드래그 정보를 ref로 읽습니다.
  const session = useRef<DragSession | undefined>(undefined);
  const dragClick = useRef(false);
  const pulseTimer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(pulseTimer.current), []);

  const flashPulse = useCallback(() => {
    setPulse(true);
    window.clearTimeout(pulseTimer.current);
    pulseTimer.current = window.setTimeout(() => setPulse(false), 260);
  }, []);

  const zones = useMemo<CollectZone[]>(() => {
    const counts = new Map<string, number>();
    savedTrends.forEach((trend) => {
      const boardId = assignments[trend.trendId] ?? UNSORTED_BOARD_ID;
      counts.set(boardId, (counts.get(boardId) ?? 0) + 1);
    });
    return [
      { boardId: UNSORTED_BOARD_ID, name: UNSORTED_BOARD_NAME, createdAt: '상시', count: counts.get(UNSORTED_BOARD_ID) ?? 0 },
      ...boards.map((board) => ({ ...board, count: counts.get(board.boardId) ?? 0 })),
    ];
  }, [assignments, boards, savedTrends]);

  /** 키워드를 특정 영역에 담습니다. 아직 저장 전이면 저장까지 함께 처리합니다. */
  const collectInto = useCallback((trend: Trend, boardId: string, boardName: string) => {
    assignTrends([trend.trendId], boardId);
    flashPulse();
    setPendingTrend(undefined);
    if (savedIds.has(trend.trendId)) {
      showToast({ message: `${boardName}(으)로 옮겼습니다.`, type: 'success' });
      return;
    }
    targetBoardName.current[trend.trendId] = boardName;
    saveMutation.mutate(trend.trendId);
  }, [assignTrends, flashPulse, saveMutation, savedIds]);

  // handleUp은 window 리스너라 최신 값을 클로저로 잡지 못하므로 ref로 읽습니다.
  const latest = useRef({ zones, collectInto });
  latest.current = { zones, collectInto };

  const toggleSave = useCallback((trend: Trend) => {
    if (savedIds.has(trend.trendId)) {
      // 분류를 지우기 전에 어디에 담겨 있었는지 기록해야 토스트에 이름을 쓸 수 있습니다.
      targetBoardName.current[trend.trendId] = boardNameOf(trend.trendId);
      assignTrends([trend.trendId], UNSORTED_BOARD_ID);
      deleteMutation.mutate(trend.trendId);
      return;
    }
    flashPulse();
    saveMutation.mutate(trend.trendId);
  }, [assignTrends, boardNameOf, deleteMutation, flashPulse, saveMutation, savedIds]);

  const startDrag = useCallback((trend: Trend, event: ReactPointerEvent) => {
    if (event.button !== 0) return;
    // 터치로는 끌지 않습니다. touch-action을 막으면 키워드에서 시작한 스크롤이 죽습니다.
    if (event.pointerType === 'touch') return;
    // 드래그 뒤에 클릭 이벤트가 오지 않는 경우도 있어, 다음 조작 전에 플래그를 되돌립니다.
    dragClick.current = false;
    session.current = { trend, origin: { x: event.clientX, y: event.clientY }, moved: false, trayWasOpen: trayOpen };
    setDragging(trend);
    setDragMoved(false);
    setGhost({ x: event.clientX + 14, y: event.clientY - 14 });

    const handleMove = (moveEvent: PointerEvent) => {
      const current = session.current;
      if (!current) return;
      setGhost({ x: moveEvent.clientX + 14, y: moveEvent.clientY - 14 });
      if (!current.moved
        && (Math.abs(moveEvent.clientX - current.origin.x) > DRAG_THRESHOLD
          || Math.abs(moveEvent.clientY - current.origin.y) > DRAG_THRESHOLD)) {
        current.moved = true;
        setDragMoved(true);
        setTrayOpen(true);
      }
      const element = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY);
      const zone = element?.closest('[data-collect-zone]')?.getAttribute('data-collect-zone') ?? undefined;
      current.target = zone;
      setDropTarget(zone);
    };

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      const current = session.current;
      session.current = undefined;
      setDragging(undefined);
      setDragMoved(false);
      setDropTarget(undefined);
      if (!current) return;

      if (!current.moved) {
        // 누르고 바로 뗐으면 드래그가 아니라 클릭이므로 상세 페이지로 이동하도록 둡니다.
        if (!current.trayWasOpen) setTrayOpen(false);
        return;
      }

      // 드래그였으므로 뒤따라오는 클릭의 링크 이동을 막습니다.
      dragClick.current = true;

      if (current.target === NEW_ZONE_ID) {
        setPendingTrend(current.trend);
        setTrayOpen(true);
        setNewZoneEditing(true);
        return;
      }

      const zone = current.target ? latest.current.zones.find((item) => item.boardId === current.target) : undefined;
      if (zone) {
        latest.current.collectInto(current.trend, zone.boardId, zone.name);
        if (!current.trayWasOpen) setTrayOpen(false);
        return;
      }

      // 영역 밖에서 놓았으면 패널을 열어둔 채로 클릭해서 마무리할 수 있게 남겨둡니다.
      setPendingTrend(current.trend);
      setTrayOpen(true);
    };

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
  }, [trayOpen]);

  const fileIntoBoard = useCallback((boardId: string) => {
    const trend = pendingTrend;
    const zone = zones.find((item) => item.boardId === boardId);
    if (!trend || !zone) return;
    collectInto(trend, zone.boardId, zone.name);
    setTrayOpen(false);
  }, [collectInto, pendingTrend, zones]);

  const createZone = useCallback((name: string) => {
    const trimmed = name.trim();
    setNewZoneEditing(false);
    if (!trimmed) return;
    const board = addBoard(trimmed);
    if (pendingTrend) {
      collectInto(pendingTrend, board.boardId, board.name);
      return;
    }
    flashPulse();
    showToast({ message: `${board.name} 영역을 만들었습니다.`, type: 'success' });
  }, [addBoard, collectInto, flashPulse, pendingTrend]);

  const value = useMemo<CollectContextValue>(() => ({
    zones,
    savedCount: savedTrends.length,
    isSaved: (trendId: string) => savedIds.has(trendId),
    boardNameOf,
    toggleSave,
    startDrag,
    consumeDragClick: () => {
      const dragged = dragClick.current;
      dragClick.current = false;
      return dragged;
    },
    draggingTrendId: dragging?.trendId,
    dragLabel: dragging?.keyword,
    dragMoved,
    pendingKeyword: pendingTrend?.keyword,
    ghost,
    dropTarget,
    trayOpen,
    openTray: () => setTrayOpen(true),
    closeTray: () => { setTrayOpen(false); setNewZoneEditing(false); setPendingTrend(undefined); },
    toggleTray: () => setTrayOpen((open) => !open),
    pulse,
    newZoneEditing,
    openNewZone: () => setNewZoneEditing(true),
    cancelNewZone: () => setNewZoneEditing(false),
    fileIntoBoard,
    createZone,
  }), [boardNameOf, createZone, dragMoved, dragging, dropTarget, fileIntoBoard, ghost, newZoneEditing, pendingTrend, pulse, savedIds, savedTrends.length, startDrag, toggleSave, trayOpen, zones]);

  return <CollectContext.Provider value={value}>{children}</CollectContext.Provider>;
}
