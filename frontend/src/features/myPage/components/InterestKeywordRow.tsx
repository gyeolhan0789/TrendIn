import { useEffect, useRef, useState } from 'react';
import type { DragEvent } from 'react';
import { Link } from 'react-router-dom';
import { Sparkline } from '../../trend/components/Sparkline';
import { INTEREST_KEYWORD_DRAG_TYPE } from '../dragTypes';
import type { InterestKeywordView, KeywordAlerts } from '../types/myPage';

interface InterestKeywordRowProps {
  view: InterestKeywordView;
  dragging: boolean;
  insertAfter?: boolean;
  isFirst: boolean;
  isLast: boolean;
  onDragStart: (keywordId: string) => void;
  onDragEnd: () => void;
  onDragOver: (keywordId: string, after: boolean) => void;
  onDragLeave: (keywordId: string) => void;
  onDrop: (targetKeywordId: string, after: boolean) => void;
  onAlertsChange: (keywordId: string, alerts: Partial<KeywordAlerts>) => void;
  onShift: (keywordId: string, offset: number) => void;
  onRemove: (keywordId: string) => void;
}

/** 커서가 줄의 아래 절반에 있으면 그 뒤에 끼워 넣습니다. */
function isAfterMidpoint(event: DragEvent<HTMLElement>) {
  const box = event.currentTarget.getBoundingClientRect();
  return event.clientY > box.top + box.height / 2;
}

/** 급등은 뱃지로 따로 표시할 만큼 두드러진 상승에만 붙입니다. */
const surgeThreshold = 200;
/** 완만한 상승까지 앰버로 칠하면 급등한 줄이 묻혀서, 선 색은 더 높은 기준으로 가릅니다. */
const risingLineThreshold = 50;

function formatGrowth(view: InterestKeywordView) {
  if (!view.trend) return '—';
  return `${view.trend.growthRate > 0 ? '+' : ''}${view.trend.growthRate}%`;
}

function describeAlerts({ trend, weekly }: KeywordAlerts) {
  if (trend && weekly) return { label: '알림 2', tone: 'is-accent' };
  if (trend) return { label: '트렌드', tone: 'is-amber' };
  if (weekly) return { label: '리포트', tone: 'is-amber' };
  return { label: '알림 없음', tone: 'is-off' };
}

function AlertToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (next: boolean) => void }) {
  return (
    <div className="mypage-menu-toggle">
      <span>{label}</span>
      <button type="button" role="switch" aria-checked={checked} aria-label={label} className={checked ? 'is-on' : ''} onClick={() => onChange(!checked)}><i /></button>
    </div>
  );
}

export function InterestKeywordRow(props: InterestKeywordRowProps) {
  const { view, dragging, insertAfter, isFirst, isLast } = props;
  const [menuOpen, setMenuOpen] = useState(false);
  const menuWrap = useRef<HTMLDivElement>(null);
  // 알림 뱃지도 같은 메뉴를 여닫아서, 바깥 클릭을 판정할 때 함께 봐야 합니다.
  const alertButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!menuWrap.current?.contains(target) && !alertButton.current?.contains(target)) setMenuOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [menuOpen]);

  const alerts = describeAlerts(view.alerts);
  const className = [
    'mypage-keyword-row',
    dragging ? 'is-dragging' : '',
    insertAfter === undefined ? '' : (insertAfter ? 'is-insert-after' : 'is-insert-before'),
  ].filter(Boolean).join(' ');

  return (
    <li
      className={className}
      draggable
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData(INTEREST_KEYWORD_DRAG_TYPE, view.keywordId);
        props.onDragStart(view.keywordId);
      }}
      onDragEnd={props.onDragEnd}
      onDragOver={(event) => {
        if (!Array.from(event.dataTransfer.types).includes(INTEREST_KEYWORD_DRAG_TYPE)) return;
        event.preventDefault();
        props.onDragOver(view.keywordId, isAfterMidpoint(event));
      }}
      onDragLeave={() => props.onDragLeave(view.keywordId)}
      onDrop={(event) => {
        event.preventDefault();
        props.onDrop(view.keywordId, isAfterMidpoint(event));
      }}
    >
      <div className="mypage-keyword-name">
        <svg className="mypage-grip" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><circle cx="9" cy="5" r="1" /><circle cx="15" cy="5" r="1" /><circle cx="9" cy="12" r="1" /><circle cx="15" cy="12" r="1" /><circle cx="9" cy="19" r="1" /><circle cx="15" cy="19" r="1" /></svg>
        {view.trend
          // 링크를 잡아도 URL이 아니라 줄이 끌리도록 링크 자체의 드래그는 끕니다.
          ? <Link to={`/trends/${view.trend.trendId}`} draggable={false}>{view.keyword}</Link>
          : <span>{view.keyword}</span>}
        {view.trend && view.trend.growthRate >= surgeThreshold && <em className="mypage-badge mypage-badge--surge">급등</em>}
        {!view.trend && <em className="mypage-badge mypage-badge--new">NEW</em>}
      </div>

      <span className={`mypage-growth${view.trend ? '' : ' is-muted'}`}>{formatGrowth(view)}</span>

      {view.trend
        ? <Sparkline trend={view.trend} width={56} height={20} color={view.trend.growthRate >= risingLineThreshold ? '#c2712c' : '#6b7686'} />
        : <span className="mypage-spark-blank" aria-hidden="true" />}

      <button type="button" ref={alertButton} className={`mypage-alert ${alerts.tone}`} aria-label={`${view.keyword} 알림 설정`} onClick={() => setMenuOpen((open) => !open)}>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
          {view.alertCount === 0 && <line x1="2" y1="2" x2="22" y2="22" />}
        </svg>
        {alerts.label}
      </button>

      <div className="mypage-more" ref={menuWrap}>
        <button type="button" aria-expanded={menuOpen} aria-label={`${view.keyword} 설정`} onClick={() => setMenuOpen((open) => !open)}>⋯</button>
        {menuOpen && (
          <div className="mypage-menu">
            <div className="mypage-menu-group">
              <p>알림 설정</p>
              <AlertToggle label="트렌드 알림" checked={view.alerts.trend} onChange={(next) => props.onAlertsChange(view.keywordId, { trend: next })} />
              <AlertToggle label="주간 리포트" checked={view.alerts.weekly} onChange={(next) => props.onAlertsChange(view.keywordId, { weekly: next })} />
            </div>
            <div className="mypage-menu-group">
              <button type="button" disabled={isFirst} onClick={() => { setMenuOpen(false); props.onShift(view.keywordId, -1); }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M12 19V5m0 0l-6 6m6-6l6 6" /></svg>
                위로 옮기기
              </button>
              <button type="button" disabled={isLast} onClick={() => { setMenuOpen(false); props.onShift(view.keywordId, 1); }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M12 5v14m0 0l6-6m-6 6l-6-6" /></svg>
                아래로 옮기기
              </button>
              <button type="button" className="is-danger" onClick={() => { setMenuOpen(false); props.onRemove(view.keywordId); }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /></svg>
                키워드 삭제
              </button>
            </div>
          </div>
        )}
      </div>
    </li>
  );
}
