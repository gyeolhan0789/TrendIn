import { useEffect, useRef, useState } from 'react';
import { AddInterestKeywordButton } from './AddInterestKeywordButton';
import { useKeywordSearch } from '../../trend/hooks/useKeywordSearch';
import { formatGrowth } from '../../trend/trendFormat';
import type { KeywordSearchItem } from '../../trend/types/keyword';

/** 글자를 칠 때마다 보내지 않고, 잠시 멈춘 뒤의 값으로만 찾습니다. */
const SEARCH_DELAY_MS = 250;

/** 아직 트렌드에 오르지 않은 키워드도 목록에 섞여 와서, 숫자 대신 왜 없는지를 알려 줍니다. */
function describeGrowth(item: KeywordSearchItem) {
  if (item.trendId === null) return '트렌드 없음';
  if (item.growthRate === null) return '증감 없음';
  return formatGrowth(item.growthRate);
}

export function KeywordSearchBar() {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  // 바깥을 누르면 닫습니다. click은 드롭다운 안의 버튼이 사라진 뒤에 와서 pointerdown을 씁니다.
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const searchQuery = useKeywordSearch(debouncedQuery);
  const results = searchQuery.data?.items ?? [];
  const trimmed = query.trim();
  const searching = trimmed.length > 0 && (searchQuery.isLoading || debouncedQuery.trim() !== trimmed);

  return (
    <div className="keywords-add" ref={wrap}>
      <div className="keywords-add-field" onClick={() => input.current?.focus()}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.35-4.35" /></svg>
        <input
          ref={input}
          type="text"
          value={query}
          aria-label="키워드 검색"
          autoComplete="off"
          placeholder="키워드를 추가해보세요"
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
        />
      </div>

      {open && trimmed.length > 0 && (
        <div className="keywords-add-menu" role="listbox" aria-label="검색 결과">
          {searching && <p className="keywords-add-none">찾는 중…</p>}
          {!searching && searchQuery.isError && <p className="keywords-add-none">키워드를 찾지 못했습니다.</p>}
          {/* 서버에 없는 말은 등록할 수 없습니다. 직접 만들어 넣는 길은 두지 않습니다. */}
          {!searching && searchQuery.isSuccess && results.length === 0 && (
            <p className="keywords-add-none">검색어와 맞는 키워드가 없습니다.</p>
          )}
          {!searching && results.map((item) => (
            <div className="keywords-add-row" key={item.keywordId}>
              <span className="keywords-add-name">
                <strong>{item.keyword}</strong>
                <small>{item.domain.name} · {describeGrowth(item)}</small>
              </span>
              <AddInterestKeywordButton keywordId={item.keywordId} keyword={item.keyword} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
