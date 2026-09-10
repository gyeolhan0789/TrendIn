import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { UNSORTED_BOARD_ID } from '../api/savedBoardStorage';
import { NEW_ZONE_ID, useCollect } from './collectContext';

function BookmarkGlyph({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 3h12v18l-6-4.5L6 21z" />
    </svg>
  );
}

export function CollectTray() {
  const collect = useCollect();
  const nameInput = useRef<HTMLInputElement>(null);
  // 커밋이 blur와 Enter로 두 번 불리는 것을 막습니다.
  const committed = useRef(false);

  useEffect(() => {
    if (collect.newZoneEditing) {
      committed.current = false;
      nameInput.current?.focus();
    }
  }, [collect.newZoneEditing]);

  const commitName = () => {
    if (committed.current) return;
    committed.current = true;
    collect.createZone(nameInput.current?.value ?? '');
  };

  const isDragging = Boolean(collect.draggingTrendId) && collect.dragMoved;
  // 담은 게 없고 패널도 닫혀 있으면 빈 북마크(회색 선)로 둡니다.
  const fabFilled = collect.trayOpen || collect.savedCount > 0;
  const awaiting = collect.pendingKeyword;

  return (
    <>
      <button
        type="button"
        className={`collect-fab${fabFilled ? ' is-filled' : ''}${isDragging ? ' is-armed' : ''}${collect.pulse ? ' is-pulsing' : ''}`}
        aria-label={`담기 패널 · 저장 ${collect.savedCount}개`}
        aria-expanded={collect.trayOpen}
        onClick={collect.toggleTray}
      >
        <BookmarkGlyph filled={fabFilled} />
        {collect.savedCount > 0 && <span className="collect-fab-count">{collect.savedCount}</span>}
      </button>

      <div className={`collect-tray${collect.trayOpen ? ' is-open' : ''}`} inert={!collect.trayOpen}>
        <div className="collect-tray-head">
          <h2>{awaiting ? `'${awaiting}' 어디에 담을까요?` : '어디에 담을까요?'}</h2>
          <button type="button" onClick={collect.closeTray}>닫기</button>
        </div>
        <p className="collect-tray-hint">
          {isDragging || awaiting ? '영역 위에 놓거나 영역을 클릭하세요.' : '키워드를 끌어다 영역에 놓아보세요.'}
          <br />
          {isDragging || awaiting ? '' : '북마크 아이콘을 누르면 미분류로 담깁니다.'}
        </p>

        {collect.zones.map((zone) => {
          const className = [
            'collect-zone',
            zone.boardId === UNSORTED_BOARD_ID ? 'collect-zone--unsorted' : '',
            collect.dropTarget === zone.boardId ? 'is-target' : '',
          ].filter(Boolean).join(' ');
          return (
            <div
              key={zone.boardId}
              className={className}
              data-collect-zone={zone.boardId}
              role={awaiting ? 'button' : undefined}
              tabIndex={awaiting ? 0 : undefined}
              onClick={() => awaiting && collect.fileIntoBoard(zone.boardId)}
              onKeyDown={(event) => {
                if (awaiting && (event.key === 'Enter' || event.key === ' ')) {
                  event.preventDefault();
                  collect.fileIntoBoard(zone.boardId);
                }
              }}
            >
              <span>
                <strong>{zone.name}</strong>
                <small>{zone.createdAt}</small>
              </span>
              <span className="collect-zone-count">{zone.count}</span>
            </div>
          );
        })}

        <div className={`collect-newzone${collect.dropTarget === NEW_ZONE_ID ? ' is-target' : ''}`} data-collect-zone={NEW_ZONE_ID}>
          {collect.newZoneEditing
            ? <input
              ref={nameInput}
              type="text"
              placeholder="예: F/W 부츠 기획"
              maxLength={24}
              aria-label="새 영역 이름"
              onBlur={commitName}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.nativeEvent.isComposing) commitName();
                if (event.key === 'Escape') { committed.current = true; collect.cancelNewZone(); }
              }}
            />
            : <button type="button" onClick={collect.openNewZone}>+ 새 영역 만들기</button>}
        </div>

        <Link className="collect-tray-link" to="/saved" onClick={collect.closeTray}>보관함 전체 보기 →</Link>
      </div>

      <div className="collect-ghost" style={{ opacity: isDragging ? 1 : 0, transform: `translate(${collect.ghost.x}px, ${collect.ghost.y}px)` }} aria-hidden="true">{collect.dragLabel}</div>
    </>
  );
}
