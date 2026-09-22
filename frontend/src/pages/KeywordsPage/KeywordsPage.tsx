import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { FilterSelect } from '../../components/common/FilterSelect';
import { InterestKeywordList } from '../../features/myPage/components/InterestKeywordList';
import { KeywordSearchBar } from '../../features/myPage/components/KeywordSearchBar';
import { RecommendedKeywords } from '../../features/myPage/components/RecommendedKeywords';
import { useInterestKeywords } from '../../features/myPage/hooks/useInterestKeywords';
import { useRecommendedKeywords } from '../../features/myPage/hooks/useRecommendedKeywords';
import { useUnreadNotificationCount } from '../../features/notification/hooks/useUnreadNotificationCount';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { pageList } from '../../utils/pageList';

const ALL_DOMAINS = '전체';

/*
 * 한 쪽에 여덟 줄. 서버가 아니라 화면에서 나눕니다 — 이 페이지의 통계 카드, 분야 거르개,
 * 등록 버튼의 "이미 담음" 판정이 전부 **전체 목록**을 봅니다. 서버 페이징으로 바꾸면 그
 * 셋이 현재 쪽만 보게 되어 개수와 거르개가 틀립니다.
 */
const PAGE_SIZE = 8;

/* 서버는 등록한 순서대로 주고 지표는 주지 않습니다. 그래서 고를 수 있는 기준이 이 둘뿐입니다. */
const sorts = [
  { value: 'recent', label: '등록순' },
  { value: 'name', label: '가나다순' },
];

function StatCard({ tone, icon, label, children }: { tone: string; icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="keywords-stat">
      <span className={`keywords-stat-icon keywords-stat-icon--${tone}`}>{icon}</span>
      <div>
        <p className="keywords-stat-label">{label}</p>
        <p className="keywords-stat-value">{children}</p>
      </div>
    </div>
  );
}

function KeywordsEmpty() {
  return (
    <div className="keywords-empty">
      <p>아직 등록한 관심 키워드가 없습니다.</p>
      <h2>위 입력칸에서 키워드를 찾아 등록해 보세요.</h2>
      <Link className="keywords-empty-action" to="/dashboard">
        트렌드 탐색에서 키워드 둘러보기
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </Link>
    </div>
  );
}

export function KeywordsPage() {
  const interestKeywordsQuery = useInterestKeywords();
  const recommendedQuery = useRecommendedKeywords();
  const domainsQuery = useDomains();
  const unreadCountQuery = useUnreadNotificationCount();
  const [selectedDomain, setSelectedDomain] = useState(ALL_DOMAINS);
  const [sort, setSort] = useState('recent');
  const [page, setPage] = useState(1);

  const keywords = useMemo(() => interestKeywordsQuery.data ?? [], [interestKeywordsQuery.data]);
  // 관심 키워드 응답에는 분야 코드만 있어, 표시 이름은 분야 목록에서 찾아 붙입니다.
  const domainNames = useMemo(
    () => new Map((domainsQuery.data ?? []).map((option) => [option.domain, option.name])),
    [domainsQuery.data],
  );

  // 등록한 키워드가 있는 분야만 거르개로 내놓습니다.
  const usedDomains = useMemo(() => [...new Set(keywords.map((keyword) => keyword.domain))], [keywords]);
  // 고른 분야의 마지막 키워드를 빼면 그 칸도 사라지므로, 갇히지 않게 전체로 되돌립니다.
  const activeDomain = usedDomains.includes(selectedDomain) ? selectedDomain : ALL_DOMAINS;

  /*
   * 몇 곳인지보다 어느 분야인지가 먼저 읽혀서, 수 대신 이름을 그대로 적습니다.
   * 지금 분야는 개발·패션 둘뿐이라 다 적어도 한 줄에 들어갑니다.
   *
   * 등록한 순서대로 두면 사람마다 개발·패션과 패션·개발로 갈립니다. 분야 목록의 순서에 맞춥니다.
   * 목록에 없는 코드는 뒤에 코드 그대로 붙입니다 — 빼면 등록한 분야가 없는 것처럼 보입니다.
   */
  const usedDomainLabel = useMemo(() => {
    if (usedDomains.length === 0) return '없음';
    // 분야 목록이 아직 오지 않았으면 이름을 못 붙입니다. 잠깐이라도 내부 코드를 내보이지 않습니다.
    if (domainNames.size === 0) return '…';
    const known = [...domainNames.keys()].filter((domain) => usedDomains.includes(domain));
    const unknown = usedDomains.filter((domain) => !domainNames.has(domain));
    return [...known, ...unknown].map((domain) => domainNames.get(domain) ?? domain).join('·');
  }, [domainNames, usedDomains]);

  const visibleKeywords = useMemo(() => {
    const filtered = activeDomain === ALL_DOMAINS
      ? keywords
      : keywords.filter((keyword) => keyword.domain === activeDomain);
    if (sort !== 'name') return filtered;
    return [...filtered].sort((a, b) => a.keyword.localeCompare(b.keyword, 'ko'));
  }, [activeDomain, keywords, sort]);

  /*
   * 쪽 번호를 상태로 두지 않고 매번 조여 냅니다. 마지막 쪽의 마지막 키워드를 빼면 그 쪽이
   * 사라지는데, 상태를 그대로 두면 빈 화면에 갇힙니다 (`SavedTrendPage` 와 같은 방식).
   */
  const totalPages = Math.max(1, Math.ceil(visibleKeywords.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const shownKeywords = visibleKeywords.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  /* 3쪽을 보다가 거르면 그 분야에 3쪽이 없어 빈 화면이 됩니다. 거르개와 정렬은 1쪽으로 돌립니다. */
  const changeSort = (value: string) => {
    setSort(value);
    setPage(1);
  };

  const changeDomain = (value: string) => {
    setSelectedDomain(value);
    setPage(1);
  };

  return (
    <div className="keywords-page">
      <section className="keywords-hero trendin-page-heading">
        <div>
          <p className="keywords-eyebrow trendin-page-eyebrow">내가 만드는 트렌드 레이더</p>
          <h1>관심 키워드</h1>
          <p className="keywords-lead trendin-page-lead">지속적으로 보고 싶은 키워드를 등록하면, 트렌드에 오를 때 알려 드립니다.</p>
        </div>
        <KeywordSearchBar />
      </section>

      <section className="keywords-stats">
        <StatCard
          tone="indigo"
          label="등록한 키워드"
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z" /></svg>}
        >
          {keywords.length}<small>개</small>
        </StatCard>

        <StatCard
          tone="emerald"
          label="관심 분야"
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M7 17l5-5 4 4 5-7" /><path d="M17 7h4v4" /></svg>}
        >
          {usedDomainLabel}
        </StatCard>

        <StatCard
          tone="blue"
          label="안 읽은 알림"
          icon={(
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" />
            </svg>
          )}
        >
          {unreadCountQuery.data ?? 0}<small>개</small>
        </StatCard>
      </section>

      <section className="keywords-toolbar">
        <div className="keywords-toolbar-title">
          <h2>내 관심 키워드</h2>
          <span className="keywords-count">{keywords.length}</span>
        </div>
        <div className="keywords-toolbar-filters">
          <FilterSelect value={sort} options={sorts} ariaLabel="정렬" onChange={changeSort} disabled={keywords.length === 0} />
          <FilterSelect
            value={activeDomain}
            options={[ALL_DOMAINS, ...usedDomains].map((domain) => ({
              value: domain,
              label: domain === ALL_DOMAINS ? '전체 분야' : domainNames.get(domain) ?? domain,
            }))}
            ariaLabel="분야"
            onChange={changeDomain}
            disabled={usedDomains.length === 0}
          />
        </div>
      </section>

      <section className="keywords-main">
        {interestKeywordsQuery.isLoading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}

        {interestKeywordsQuery.isError && (
          <div className="trendin-state is-error" role="alert">
            <p>관심 키워드를 불러오지 못했습니다.</p>
            <button type="button" onClick={() => interestKeywordsQuery.refetch()}>다시 시도</button>
          </div>
        )}

        {interestKeywordsQuery.isSuccess && (
          <>
            {keywords.length === 0 && <KeywordsEmpty />}
            {keywords.length > 0 && visibleKeywords.length === 0 && <p className="keywords-filter-empty">이 분야에 등록한 키워드가 없습니다.</p>}
            {shownKeywords.length > 0 && <InterestKeywordList keywords={shownKeywords} domainNames={domainNames} />}
          </>
        )}
      </section>

      {interestKeywordsQuery.isSuccess && totalPages > 1 && (
        <section className="keywords-pagination">
          <div className="trendin-pages">
            {pageList(currentPage, totalPages).map((item, index) => (item === 'gap'
              ? <span className="trendin-page-gap" key={`gap-${index}`}>···</span>
              : (
                <button
                  key={item}
                  type="button"
                  className={item === currentPage ? 'is-current' : ''}
                  aria-current={item === currentPage ? 'page' : undefined}
                  onClick={() => setPage(item)}
                >
                  {item}
                </button>
              )))}
          </div>
        </section>
      )}

      {recommendedQuery.isSuccess && (
        <section className="keywords-recommend-section">
          <RecommendedKeywords recommendations={recommendedQuery.data} />
        </section>
      )}
    </div>
  );
}
