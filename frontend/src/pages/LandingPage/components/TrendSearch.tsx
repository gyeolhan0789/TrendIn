import { useEffect, useState } from 'react';
import { useKeywordSearch } from '../../../features/trend/hooks/useKeywordSearch';

type Content = { title: string; description: string; tag: string };

const SEARCH_DELAY_MS = 280;

export function TrendSearch({ contents }: { contents: Content[] }) {
  const [input, setInput] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const query = input.trim();

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  const searchQuery = useKeywordSearch(debouncedQuery);
  const searching = query.length > 0 && (debouncedQuery !== query || searchQuery.isPending || searchQuery.isFetching);
  const settled = query.length > 0 && !searching && searchQuery.isSuccess;
  const foundKeywords = settled ? searchQuery.data.items : [];
  const normalized = query.toLocaleLowerCase().replace(/\s/g, '');
  const foundContents = settled
    ? contents.filter((item) => `${item.title} ${item.description} ${item.tag}`.toLocaleLowerCase().replace(/\s/g, '').includes(normalized))
    : [];
  return <section className="trend-search" aria-label="트렌드 검색">
    <form role="search" onSubmit={(event) => { event.preventDefault(); setDebouncedQuery(query); }}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></svg>
      <label className="visually-hidden" htmlFor="trend-query">관심 있는 패션 키워드 검색</label>
      <input id="trend-query" type="search" value={input} onChange={(event) => setInput(event.target.value)} placeholder="관심 있는 키워드를 검색해보세요." />
      <button className="search-submit" type="submit" aria-label="검색"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6"/></svg></button>
    </form>
    {query && <div className="search-results">
      <div className="search-results-heading"><p role="status">‘{query}’ {settled ? `검색 결과 · ${foundKeywords.length + foundContents.length}개` : searchQuery.isError && !searching ? '검색 오류' : '검색 중'}</p><button type="button" onClick={() => { setInput(''); setDebouncedQuery(''); }}>닫기</button></div>
      {searching && <p className="search-empty">찾는 중…</p>}
      {!searching && searchQuery.isError && <p className="search-empty">검색 결과를 불러오지 못했습니다.</p>}
      {settled && foundKeywords.length > 0 && <div className="search-keywords">{foundKeywords.map((item) => <span key={item.keywordId}>{item.keyword}</span>)}</div>}
      {settled && foundContents.length > 0 && <ul>{foundContents.map((item) => <li key={item.title}><strong>{item.title}</strong><p>{item.description}</p></li>)}</ul>}
      {settled && foundKeywords.length === 0 && foundContents.length === 0 && <p className="search-empty">검색어와 맞는 키워드가 없습니다.</p>}
      {settled && searchQuery.data.hasNext && <small>키워드 결과가 더 있습니다. 검색어를 조금 더 입력해 주세요.</small>}
    </div>}
  </section>;
}
