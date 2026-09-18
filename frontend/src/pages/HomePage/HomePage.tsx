import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import heroWave from '../../assets/flowing-wave.webp';
import { CylinderCarousel } from '../../components/common/CylinderCarousel';
import { FilterSelect } from '../../components/common/FilterSelect';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { KeywordSuggestMenu } from '../../features/trend/components/KeywordSuggestMenu';
import { TOP_COUNT, TrendRankBoard } from '../../features/trend/components/TrendRankBoard';
import { useKeywordSuggest } from '../../features/trend/hooks/useKeywordSuggest';
import { useTrends } from '../../features/trend/hooks/useTrends';
import { useTrendDetailLink } from '../../features/trend/trendDetailLink';
import { ANALYSIS_PERIODS, parsePeriod, resolveDomainCode } from '../../constants/filterCodes';
import type { PeriodCode } from '../../constants/filterCodes';
import { TREND_TYPES } from '../../features/trend/types/trend';
import type { TrendAnalysisWindow, TrendType } from '../../features/trend/types/trend';
import type { KeywordSearchItem } from '../../features/trend/types/keyword';

const periodLabels: Record<PeriodCode, string> = {
  '24H': '최근 24시간',
  '7D': '최근 7일',
  '30D': '최근 30일',
};

/** 캐러셀의 점에 붙는 짧은 이름입니다. 판 안의 제목은 '인기 트렌드'처럼 길게 둡니다. */
const typeLabels: Record<TrendType, string> = {
  CURRENT: '인기',
  NEW: '신규',
  RISING: '급상승',
};

/** 입력칸이 aria-controls 로 가리킬 이름입니다. 한 쪽에 검색 상자가 하나라 고정 값으로 둡니다. */
const SUGGEST_ID = 'explore-keyword-suggest';

function formatWindowDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[2]}.${match[3]}` : value;
}

function describeWindow(window: TrendAnalysisWindow | null | undefined) {
  if (!window) return undefined;
  return `${formatWindowDate(window.recentStart)} ~ ${formatWindowDate(window.recentEnd)} 집계 · 직전 구간과 비교`;
}

function ArrowIcon({ size = 14, color = 'currentColor', width = 2.5 }: { size?: number; color?: string; width?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function BoltIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" />
    </svg>
  );
}

function SearchIcon({ size = 16, color = '#4F46E5' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const openDetail = useTrendDetailLink();
  const domainsQuery = useDomains();
  const domains = useMemo(() => domainsQuery.data ?? [], [domainsQuery.data]);

  const period = parsePeriod(searchParams.get('period'));
  const rawType = searchParams.get('status')?.toUpperCase() ?? '';
  const type: TrendType = (TREND_TYPES as readonly string[]).includes(rawType) ? (rawType as TrendType) : 'CURRENT';
  const query = searchParams.get('q') ?? '';
  const [draft, setDraft] = useState(query);

  // 분야 목록을 받기 전에는 고를 분야가 없어 조회를 멈춰 둡니다.
  const domain = resolveDomainCode(searchParams.get('category'), domains);

  /*
   * 집계 구간과 빠른 탐색 꼬리표는 지금 보는 판의 것을 씁니다. 순위판이 처음 부르는 조회와
   * 조건이 같아 캐시를 함께 쓰므로, 이 줄 때문에 서버를 한 번 더 부르지는 않습니다.
   */
  const shownQuery = useTrends(domain ? { domain, type, period, page: 0, size: TOP_COUNT } : undefined);
  const windowLabel = describeWindow(shownQuery.data?.analysisWindow);
  const quickTags = useMemo(
    () => (shownQuery.data?.trends ?? []).map((trend) => trend.keyword),
    [shownQuery.data],
  );

  const updateParams = (updates: Record<string, string | undefined>, replace = false) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === undefined) next.delete(key);
      else next.set(key, value);
    });
    setSearchParams(next, { replace });
  };

  /*
   * 자동완성은 이 쪽 목록이 아니라 서버 전체에서 찾습니다. 고른 말이 트렌드에 올라 있으면
   * 상세를 바로 열고, 아직 오르지 않았으면 이 쪽 목록을 그 말로 걸러 없다는 것을 보여 줍니다.
   */
  const selectSuggestion = (item: KeywordSearchItem) => {
    setDraft(item.keyword);
    if (item.trendId === null) {
      updateParams({ q: item.keyword });
      return;
    }
    const { to, state } = openDetail(item.trendId);
    navigate(to, { state });
  };

  const suggest = useKeywordSuggest(draft, selectSuggestion);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    suggest.hide();
    updateParams({ q: draft.trim() || undefined });
  };

  const runQuickTag = (keyword: string) => {
    setDraft(keyword);
    updateParams({ q: keyword });
  };

  /* 캐러셀 자리는 주소창의 status 와 한 몸입니다. 돌릴 때마다 뒤로가기가 쌓이지 않게 바꿔치기합니다. */
  const slides = TREND_TYPES.map((code) => ({
    key: code,
    label: typeLabels[code],
    node: <TrendRankBoard type={code} domain={domain} period={period} query={query} />,
  }));

  return (
    <div className="explore-page">
      <section className="explore-hero">
        <div>
          <p className="explore-hero-eyebrow">트렌드를 더 빠르게, 더 깊이</p>
          <h1>트렌드 탐색</h1>
          <p className="explore-hero-lead">{windowLabel ?? '인기·신규·급상승 트렌드를 한눈에 확인하세요.'}</p>
        </div>
        <div className="explore-hero-visual">
          <img src={heroWave} alt="" />
          <div className="explore-hero-note">
            <p>지금 이 순간에도<br />새로운 트렌드가 만들어지고 있어요.</p>
          </div>
        </div>
      </section>

      <section className="explore-searchbar">
        {/* 목록은 검색 상자에 폭을 맞춥니다. 칸(section)에는 좌우 여백이 있어 그 기준으로 두면 밖으로 삐져나옵니다. */}
        <div className="explore-search-shell" ref={suggest.box}>
          <form onSubmit={submitSearch} role="search">
            <SearchIcon size={20} color="#9ca3af" />
            <input
              type="text"
              value={draft}
              placeholder="키워드를 검색해보세요."
              aria-label="키워드 검색"
              role="combobox"
              aria-expanded={suggest.visible}
              aria-controls={SUGGEST_ID}
              aria-autocomplete="list"
              aria-activedescendant={suggest.activeIndex >= 0 ? `${SUGGEST_ID}-${suggest.activeIndex}` : undefined}
              autoComplete="off"
              onChange={(event) => { setDraft(event.target.value); suggest.show(); }}
              onFocus={suggest.show}
              onKeyDown={suggest.handleKeyDown}
            />
            {query && (
              <button type="button" className="explore-search-clear" onClick={() => { setDraft(''); suggest.hide(); updateParams({ q: undefined }); }}>
                지우기
              </button>
            )}
            <button type="submit" className="explore-search-go" aria-label="검색">
              <ArrowIcon size={16} color="#fff" />
            </button>
          </form>

          {suggest.visible && (
            <KeywordSuggestMenu
              id={SUGGEST_ID}
              query={draft.trim()}
              items={suggest.items}
              status={suggest.status}
              activeIndex={suggest.activeIndex}
              onHover={suggest.setActiveIndex}
              onSelect={suggest.select}
            />
          )}
        </div>

        {/* 조건 고르는 칸은 검색 상자와 한 줄에 서고, 오른쪽 끝으로 붙습니다. */}
        <div className="explore-filters">
          <FilterSelect
            label="기간"
            value={period}
            options={ANALYSIS_PERIODS.map((code) => ({ value: code, label: periodLabels[code] }))}
            onChange={(value) => updateParams({ period: value })}
          />

          <div className="trendin-filter">
            <span className="trendin-filter-label">카테고리</span>
            <div className="explore-chips" role="group" aria-label="카테고리">
              {domains.map((option) => (
                <button
                  type="button"
                  key={option.domain}
                  className={`explore-cat${option.domain === domain ? ' is-selected' : ''}`}
                  aria-pressed={option.domain === domain}
                  onClick={() => updateParams({ category: option.domain })}
                >
                  {option.name}
                </button>
              ))}
              {domains.length === 0 && <span className="trendin-filter-label">분야를 불러오는 중…</span>}
            </div>
          </div>
        </div>
      </section>

      <section className="explore-main">
        {domainsQuery.isError && (
          <div className="trendin-state is-error" role="alert">
            <p>분야를 불러오지 못했습니다.</p>
            <button type="button" onClick={() => void domainsQuery.refetch()}>다시 시도</button>
          </div>
        )}
        {!domainsQuery.isError && (
          <CylinderCarousel
            slides={slides}
            index={Math.max(0, TREND_TYPES.indexOf(type))}
            onIndexChange={(next) => updateParams({ status: TREND_TYPES[next] }, true)}
            ariaLabel="트렌드 갈래"
          />
        )}
      </section>

      <section className="explore-extra">
        <div className="explore-panel">
          <div className="explore-panel-head"><SearchIcon /><span>빠른 탐색</span></div>
          <p className="explore-panel-lead">지금 이 판에 오른 키워드로 바로 걸러 보세요.</p>
          <div className="explore-quick">
            {quickTags.map((keyword) => (
              <button type="button" key={keyword} onClick={() => runQuickTag(keyword)}>{keyword}</button>
            ))}
            {quickTags.length === 0 && <span className="explore-panel-lead">보여 줄 키워드가 아직 없습니다.</span>}
          </div>
        </div>

        <Link className="explore-cta" to="/keywords">
          <span className="explore-cta-glow" />
          <p><BoltIcon /> 지금, 당신만의<br />관심 키워드를 등록해보세요.</p>
          <p className="explore-cta-sub">맞춤 트렌드 알림을 받을 수 있습니다.</p>
          <ArrowIcon size={14} color="#4338ca" />
        </Link>
      </section>
    </div>
  );
}
