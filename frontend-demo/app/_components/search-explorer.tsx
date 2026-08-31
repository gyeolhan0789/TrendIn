'use client';

import { useRef, useState } from 'react';
import Link from './page-link';
import { worldHref } from '../trend-navigation';
import AppHeader from './app-header';
import { ExploreFooter, useTrendWorkspace, WorkspaceOverlays } from './trend-workspace';
import { categories, getCategory, type CategoryId } from '../trends';
import { kindLabels, searchTrends, type SearchKind, type SearchScope, type SearchSort } from '../search-data';
const format = (n: number) => new Intl.NumberFormat('ko-KR').format(n);

export default function SearchExplorer({ initialQuery = '', initialCategory }: { initialQuery?: string; initialCategory?: CategoryId }) {
  const w = useTrendWorkspace();
  const [query, setQuery] = useState(initialQuery);
  const [scope, setScope] = useState<SearchScope>(initialCategory ?? 'interests');
  const [kind, setKind] = useState<SearchKind>('all');
  const [sort, setSort] = useState<SearchSort>('relevance');
  const [savedOnly, setSavedOnly] = useState(false);
  const [limit, setLimit] = useState(12);
  const input = useRef<HTMLInputElement>(null);
  const results = searchTrends({ query, scope, interests: w.prefs.interests, kind, sort, savedOnly, saved: w.prefs.saved });
  const remember = (term: string) => {
    const clean = term.trim().slice(0, 100);
    if (clean) w.updatePrefs({ recentSearches: [clean, ...w.prefs.recentSearches.filter(q => q !== clean)].slice(0, 8) });
  };
  const applyQuery = (term: string) => { setQuery(term); setLimit(12); remember(term); input.current?.focus(); };
  const reset = () => { setQuery(''); setScope('interests'); setKind('all'); setSavedOnly(false); setSort('relevance'); setLimit(12); input.current?.focus(); };
  const category = getCategory(w.prefs.active);
  const recommendations = [...category.top.slice(0, 2).map(t => t[0]), category.fresh[0][0], category.rising[0][0]];
  const scopeName = scope === 'interests' ? '내 관심 분야' : getCategory(scope).name;
  return <div className="explore-page search-page">
    <a className="skip-link" href="#main-content">본문으로 바로가기</a>
    <AppHeader active="search" savedCount={w.savedTrends.length} onSaved={() => w.setSheet({ type: 'saved' })} onSettings={() => w.setSheet({ type: 'settings' })}/>
    <main className="explore-main" id="main-content">
      <section className="explore-heading"><div><p className="eyebrow">FOLLOW YOUR CURIOSITY</p><h1>다음 관심사는, 어디에<span className="accent">?</span></h1><p>키워드 하나에서 시작해, 새로운 흐름까지 찾아보세요.</p></div><span className="sample-stamp">TREND FINDER <span>탐색을 위한 예시 데이터</span></span></section>
      <form className="trend-search-form" role="search" onSubmit={e => { e.preventDefault(); remember(query); }}><label htmlFor="trend-query" className="sr-only">트렌드 키워드 검색</label><span className="search-symbol" aria-hidden="true"/><input ref={input} id="trend-query" type="search" value={query} onChange={e => { setQuery(e.target.value); setLimit(12); }} placeholder="어떤 흐름이 궁금하세요?" autoComplete="off" maxLength={100} aria-describedby="search-hint"/>{query && <button className="search-clear" type="button" aria-label="검색어 지우기" onClick={() => { setQuery(''); setLimit(12); input.current?.focus(); }}>×</button>}<button className="search-submit" type="submit">검색 <span aria-hidden="true">↗</span></button></form>
      <div className="search-hint" id="search-hint"><span>키워드·설명·연관어로 검색해요. 일부 키워드는 한글로도 찾을 수 있어요.</span><span>최근 24시간 예시</span></div>
      <div className="search-scopes" aria-label="검색 분야"><button className={scope === 'interests' ? 'selected' : ''} aria-pressed={scope === 'interests'} onClick={() => { setScope('interests'); setLimit(12); }}>내 관심 분야 <span>{w.prefs.interests.length}</span></button><span className="scope-divider"/>{categories.map(c => <button key={c.id} className={scope === c.id ? 'selected' : ''} aria-pressed={scope === c.id} onClick={() => { setScope(c.id); setLimit(12); }}>{c.name}</button>)}</div>
      <div className="search-layout">
        <section className="search-results" aria-label="검색 결과">
          <div className="search-results-head"><h2>{query.trim() ? '검색 결과' : '발견할 수 있는 흐름'} <span aria-live="polite">{results.length}</span></h2><label className="search-sort">정렬<select value={sort} onChange={e => { setSort(e.target.value as SearchSort); setLimit(12); }}><option value="relevance">관련도순</option><option value="mentions">언급량순</option><option value="growth">증가율순</option></select></label></div>
          <div className="search-result-filters"><div aria-label="트렌드 유형">{(['all', 'top', 'new', 'rising'] as const).map(k => <button key={k} className={kind === k ? 'selected' : ''} aria-pressed={kind === k} onClick={() => { setKind(k); setLimit(12); }}>{k === 'all' ? '모든 흐름' : kindLabels[k]}</button>)}</div><label className="saved-only"><input type="checkbox" checked={savedOnly} onChange={e => { setSavedOnly(e.target.checked); setLimit(12); }}/>저장한 항목만</label></div>
          <p className="search-context" role="status">{scopeName} · {kind === 'all' ? '모든 유형' : kindLabels[kind]}{query.trim() ? ` · “${query.trim()}”` : ''}{savedOnly ? ' · 저장한 항목' : ''}</p>
          {results.length ? <><ul className="search-result-list">{results.slice(0, limit).map(t => <li key={t.id}><button className="search-result-open" onClick={() => { remember(query); w.openTrend(t); }}><span className="search-result-copy"><span className="search-result-meta">{getCategory(t.category).name}<i/> {t.tag}<span className={`result-kind kind-${t.kind}`}>{kindLabels[t.kind]}</span></span><strong>{t.name}<span aria-hidden="true">↗</span></strong><span className="search-result-description">{t.sub}</span></span><span className="search-result-metrics"><span><small>언급량</small><b>{format(t.mentions)}<small>건</small></b></span><span><small>{t.kind === 'new' ? '탐지 유형' : '이전 24시간 대비'}</small><b className="accent">{t.kind === 'new' ? 'NEW' : `+${t.growth}%`}</b></span></span></button><div className="search-row-actions"><Link href={worldHref(t)} aria-label={`${t.name} 세계 추이 보기`}>세계 추이 ↗</Link><button className={`result-save ${w.prefs.saved.includes(t.id) ? 'selected' : ''}`} aria-label={`${t.name} ${w.prefs.saved.includes(t.id) ? '저장 해제' : '저장'}`} aria-pressed={w.prefs.saved.includes(t.id)} onClick={() => w.toggleSave(t)}><svg width="16" height="19" viewBox="0 0 16 19" aria-hidden="true"><path d="M3 1.5h10v15l-5-3-5 3z" fill={w.prefs.saved.includes(t.id) ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></svg></button></div></li>)}</ul>{results.length > limit && <button className="search-more" onClick={() => setLimit(limit + 12)}>더 많은 흐름 보기 <span>{Math.min(limit, results.length)} / {results.length} ＋</span></button>}</>
            : <div className="search-empty"><span aria-hidden="true">↗</span><h3>{savedOnly ? '조건에 맞는 저장 항목이 없어요' : '아직 찾지 못한 흐름이에요'}</h3><p>{savedOnly ? '저장한 항목만 보기 조건을 해제하거나, 다른 키워드로 찾아보세요.' : '검색어를 짧게 바꾸거나 다른 관심 분야를 선택해보세요. 현재는 예시 데이터 안에서만 검색합니다.'}</p><button className="primary-button" onClick={reset}>검색 조건 초기화 ↗</button></div>}
        </section>
        <aside className="search-sidebar"><section><p className="explore-kicker">A PLACE TO START</p><h2>이런 흐름은 어때요?</h2><p>{category.name} 분야에서 시작하는 작은 발견.</p><div className="search-suggestions">{recommendations.map((word, i) => <button key={word} onClick={() => { setScope(category.id); setKind('all'); setSavedOnly(false); applyQuery(word); }}><span>0{i + 1}</span><strong>{word}</strong><span>↗</span></button>)}</div></section>
          <section className="recent-searches"><div><h2>최근 검색</h2>{w.prefs.recentSearches.length > 0 && <button onClick={() => w.updatePrefs({ recentSearches: [] })}>전체 삭제</button>}</div>{w.prefs.recentSearches.length ? <ul>{w.prefs.recentSearches.map(term => <li key={term}><button onClick={() => applyQuery(term)}><span aria-hidden="true">↶</span>{term}</button><button aria-label={`${term} 최근 검색 삭제`} onClick={() => w.updatePrefs({ recentSearches: w.prefs.recentSearches.filter(q => q !== term) })}>×</button></li>)}</ul> : <p>궁금한 키워드를 입력하고 검색하면<br/>다시 찾기 쉽게 여기에 남겨둘게요.</p>}<small>최근 검색은 이 브라우저에만 저장됩니다.</small></section>
          <div className="search-tip"><span>SEARCH NOTE</span><p>익숙한 단어를 조금 다르게.<br/>새로운 관심사는 작은 검색에서 시작돼요.</p></div>
        </aside>
      </div><ExploreFooter/>
    </main><WorkspaceOverlays workspace={w}/>
  </div>;
}
