import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthSession } from '../../../features/auth/hooks/useAuthSession';
import { filterDetailKeywords } from '../../../features/trend/detailKeyword';
import { useKeywordSearch } from '../../../features/trend/hooks/useKeywordSearch';
import { useTrendDetailLink } from '../../../features/trend/trendDetailLink';

const SEARCH_DELAY_MS = 280;

export function TrendSearch() {
  const session = useAuthSession();
  const location = useLocation();
  const navigate = useNavigate();
  const openDetail = useTrendDetailLink();
  const [input, setInput] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const query = input.trim();

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  const searchQuery = useKeywordSearch(debouncedQuery, Boolean(session));
  const searching = query.length > 0 && (debouncedQuery !== query || searchQuery.isPending || searchQuery.isFetching);
  const settled = query.length > 0 && !searching && searchQuery.isSuccess;
  const foundKeywords = settled ? filterDetailKeywords(searchQuery.data.items) : [];
  const requireLogin = () => {
    if (session) return false;
    navigate('/login', {
      state: { from: `${location.pathname}${location.search}` },
    });
    return true;
  };

  return <section className="trend-search" aria-label="트렌드 검색">
    <form role="search" onSubmit={(event) => { event.preventDefault(); if (!requireLogin()) setDebouncedQuery(query); }}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></svg>
      <label className="visually-hidden" htmlFor="trend-query">관심 있는 패션 키워드 검색</label>
      <input
        id="trend-query"
        type="search"
        value={input}
        onFocus={requireLogin}
        onChange={(event) => { if (!requireLogin()) setInput(event.target.value); }}
        placeholder="관심 있는 키워드를 검색해보세요."
      />
      <button className="search-submit" type="submit" aria-label="검색"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6"/></svg></button>
    </form>
    {query && <div className="search-results">
      <div className="search-results-heading"><p role="status">‘{query}’ {settled ? `검색 결과 · ${foundKeywords.length}개` : searchQuery.isError && !searching ? '검색 오류' : '검색 중'}</p><button type="button" onClick={() => { setInput(''); setDebouncedQuery(''); }}>닫기</button></div>
      {searching && <p className="search-empty">찾는 중…</p>}
      {!searching && searchQuery.isError && <p className="search-empty">검색 결과를 불러오지 못했습니다.</p>}
      {settled && foundKeywords.length > 0 && <div className="search-keywords">{foundKeywords.map((item) => (
        <Link key={item.keywordId} {...openDetail(item.trendId)}>{item.keyword}</Link>
      ))}</div>}
      {settled && foundKeywords.length === 0 && <p className="search-empty">검색어와 맞는 트렌드가 없습니다.</p>}
      {settled && searchQuery.data.hasNext && <small>키워드 결과가 더 있습니다. 검색어를 조금 더 입력해 주세요.</small>}
    </div>}
  </section>;
}
