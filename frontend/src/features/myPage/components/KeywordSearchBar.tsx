import { useEffect, useMemo, useRef, useState } from 'react';
import type { Trend } from '../../trend/types/trend';

interface KeywordSearchBarProps {
  catalog: Trend[];
  /** 이미 등록한 키워드는 '등록됨'으로 표시하고 다시 담지 않습니다. */
  registeredTrendIds: Set<string>;
  registeredKeywords: Set<string>;
  onAdd: (input: { keyword: string; trendId?: string }) => void;
}

const maxResults = 5;

function formatGrowth(trend: Trend) {
  if (trend.change === 'NEW') return 'NEW';
  return `${trend.growthRate > 0 ? '+' : ''}${trend.growthRate}%`;
}

export function KeywordSearchBar({ catalog, registeredTrendIds, registeredKeywords, onAdd }: KeywordSearchBarProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  // 바깥을 누르면 닫습니다. click은 드롭다운 안의 버튼이 사라진 뒤에 와서 pointerdown을 씁니다.
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const trimmed = query.trim();
  const results = useMemo(() => {
    if (!trimmed) return [];
    const needle = trimmed.toLowerCase();
    return catalog.filter((trend) => trend.keyword.toLowerCase().includes(needle)).slice(0, maxResults);
  }, [catalog, trimmed]);

  // 같은 이름이 이미 후보에 있으면 '새 키워드로 등록'은 군더더기라 감춥니다.
  const canCreate = Boolean(trimmed) && !catalog.some((trend) => trend.keyword.toLowerCase() === trimmed.toLowerCase());

  const add = (input: { keyword: string; trendId?: string }) => {
    onAdd(input);
    setQuery('');
    setOpen(false);
  };

  return (
    <div className="mypage-search" ref={wrap}>
      <div className="mypage-search-field" onClick={() => input.current?.focus()}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
        <input
          ref={input}
          type="text"
          value={query}
          aria-label="키워드 검색"
          placeholder="키워드 검색 또는 직접 입력…"
          onFocus={() => setOpen(true)}
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') { setOpen(false); return; }
            if (event.key !== 'Enter' || event.nativeEvent.isComposing || !trimmed) return;
            // 목록에 없는 말이면 입력한 그대로, 이미 있는 말이면 후보 첫 줄을 등록합니다.
            if (canCreate) {
              if (!registeredKeywords.has(trimmed)) add({ keyword: trimmed });
              return;
            }
            const first = results.find((trend) => !registeredTrendIds.has(trend.trendId));
            if (first) add({ keyword: first.keyword, trendId: first.trendId });
          }}
        />
      </div>

      {open && trimmed && (
        <div className="mypage-search-menu">
          {results.length > 0 && (
            <div className="mypage-search-group">
              <p>검색 결과</p>
              {results.map((trend) => {
                const registered = registeredTrendIds.has(trend.trendId);
                return (
                  <div className="mypage-search-row" key={trend.trendId}>
                    <span className="mypage-search-name">
                      {trend.keyword}
                      {trend.growthRate >= 200 && <em className="mypage-badge mypage-badge--surge">급등</em>}
                      <small className={trend.change === 'NEW' ? 'is-muted' : ''}>{formatGrowth(trend)}</small>
                    </span>
                    <button
                      type="button"
                      className={`mypage-search-add${registered ? ' is-registered' : ''}`}
                      disabled={registered}
                      onClick={() => add({ keyword: trend.keyword, trendId: trend.trendId })}
                    >
                      {registered
                        ? <><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg>등록됨</>
                        : <><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>추가</>}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {canCreate && (
            <div className="mypage-search-group mypage-search-group--create">
              <button
                type="button"
                className="mypage-search-row mypage-search-create"
                disabled={registeredKeywords.has(trimmed)}
                onClick={() => add({ keyword: trimmed })}
              >
                <span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
                  {registeredKeywords.has(trimmed) ? `"${trimmed}"은(는) 이미 등록했습니다` : `"${trimmed}"를 새 키워드로 등록`}
                </span>
                <small>Enter</small>
              </button>
            </div>
          )}

          {results.length === 0 && !canCreate && <p className="mypage-search-none">이미 등록한 키워드입니다.</p>}
        </div>
      )}
    </div>
  );
}
