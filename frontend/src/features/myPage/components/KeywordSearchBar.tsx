import { useEffect, useRef, useState } from 'react';
import { AddInterestKeywordButton } from './AddInterestKeywordButton';
import { useKeywordSearch } from '../../trend/hooks/useKeywordSearch';
import type { KeywordSearchItem } from '../../trend/types/keyword';

/** 글자를 칠 때마다 보내지 않고, 잠시 멈춘 뒤의 값으로만 찾습니다. */
const SEARCH_DELAY_MS = 250;

function formatGrowth(item: KeywordSearchItem) {
  if (item.trendId === null) return '트렌드 없음';
  if (item.growthRate === null) return '증감 없음';
  return `${item.growthRate > 0 ? '+' : ''}${item.growthRate}%`;
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
    <div className="mypage-search" ref={wrap}>
      <div className="mypage-search-field" onClick={() => input.current?.focus()}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
        <input
          ref={input}
          type="text"
          value={query}
          aria-label="키워드 검색"
          placeholder="등록할 키워드를 찾아보세요"
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
        />
      </div>

      {open && trimmed.length > 0 && (
        <div className="mypage-search-menu" role="listbox" aria-label="검색 결과">
          {searching && <p className="mypage-search-none">찾는 중…</p>}
          {!searching && searchQuery.isError && <p className="mypage-search-none">키워드를 찾지 못했습니다.</p>}
          {/* 서버에 없는 말은 등록할 수 없습니다. 직접 만들어 넣는 길은 두지 않습니다. */}
          {!searching && searchQuery.isSuccess && results.length === 0 && (
            <p className="mypage-search-none">검색어와 맞는 키워드가 없습니다.</p>
          )}
          {!searching && results.map((item) => (
            <div className="mypage-search-row" key={item.keywordId}>
              <span className="mypage-search-name">
                <strong>{item.keyword}</strong>
                <small>{item.domain.name} · {formatGrowth(item)}</small>
              </span>
              <AddInterestKeywordButton keywordId={item.keywordId} keyword={item.keyword} />
            </div>
          ))}
          {!searching && searchQuery.data?.hasNext && (
            <p className="mypage-search-none">결과가 더 있습니다. 검색어를 조금 더 적어 보세요.</p>
          )}
        </div>
      )}
    </div>
  );
}
