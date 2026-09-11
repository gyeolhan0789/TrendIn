import { useState } from 'react';
import type { InterestKeywordView, KeywordAlerts } from '../types/myPage';
import { InterestKeywordRow } from './InterestKeywordRow';

interface InterestKeywordListProps {
  views: InterestKeywordView[];
  /** 필터로 일부만 보여줄 때도 위/아래로 옮기기는 전체 목록 기준이어야 합니다. */
  totalCount: number;
  indexOf: (keywordId: string) => number;
  onAlertsChange: (keywordId: string, alerts: Partial<KeywordAlerts>) => void;
  onMove: (keywordId: string, targetKeywordId: string, after: boolean) => void;
  onShift: (keywordId: string, offset: number) => void;
  onRemove: (keywordId: string) => void;
}

export function InterestKeywordList(props: InterestKeywordListProps) {
  const { views, totalCount, indexOf } = props;
  const [draggingId, setDraggingId] = useState<string>();
  const [insertAt, setInsertAt] = useState<{ keywordId: string; after: boolean }>();

  const endDrag = () => {
    setDraggingId(undefined);
    setInsertAt(undefined);
  };

  return (
    <ul className="mypage-keyword-list">
      {views.map((view) => {
        const index = indexOf(view.keywordId);
        return (
          <InterestKeywordRow
            key={view.keywordId}
            view={view}
            dragging={draggingId === view.keywordId}
            // 끌고 있는 줄 자신에게는 끼워 넣기 표시를 하지 않습니다.
            insertAfter={insertAt?.keywordId === view.keywordId && draggingId !== view.keywordId ? insertAt.after : undefined}
            isFirst={index <= 0}
            isLast={index === totalCount - 1}
            onDragStart={setDraggingId}
            onDragEnd={endDrag}
            onDragOver={(keywordId, after) => setInsertAt({ keywordId, after })}
            onDragLeave={(keywordId) => setInsertAt((current) => (current?.keywordId === keywordId ? undefined : current))}
            onDrop={(targetKeywordId, after) => {
              if (draggingId) props.onMove(draggingId, targetKeywordId, after);
              endDrag();
            }}
            onAlertsChange={props.onAlertsChange}
            onShift={props.onShift}
            onRemove={props.onRemove}
          />
        );
      })}
    </ul>
  );
}
