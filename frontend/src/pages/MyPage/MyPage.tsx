import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { PageContainer } from '../../components/layout/PageContainer';
import { InterestKeywordList } from '../../features/myPage/components/InterestKeywordList';
import { KeywordSearchBar } from '../../features/myPage/components/KeywordSearchBar';
import { MyPageSidebar } from '../../features/myPage/components/MyPageSidebar';
import { RecommendedKeywords } from '../../features/myPage/components/RecommendedKeywords';
import { useInterestKeywords } from '../../features/myPage/hooks/useInterestKeywords';
import { useMyProfile } from '../../features/myPage/hooks/useMyProfile';
import { useRecommendedKeywords } from '../../features/myPage/hooks/useRecommendedKeywords';
import { useDomains } from '../../features/onboarding/hooks/useDomains';

const ALL_DOMAINS = '전체';

function MyPageEmpty() {
  return (
    <div className="mypage-empty">
      <p>아직 등록한 관심 키워드가 없습니다.</p>
      <h2>위 검색창에서 키워드를 찾아 등록해 보세요.</h2>
      <Link className="mypage-empty-action" to="/">대시보드에서 키워드 둘러보기<span aria-hidden="true">→</span></Link>
    </div>
  );
}

export function MyPage() {
  const profileQuery = useMyProfile();
  const interestKeywordsQuery = useInterestKeywords();
  const recommendedQuery = useRecommendedKeywords();
  const domainsQuery = useDomains();
  const [selectedDomain, setSelectedDomain] = useState(ALL_DOMAINS);

  const keywords = useMemo(() => interestKeywordsQuery.data ?? [], [interestKeywordsQuery.data]);
  // 관심 키워드 응답에는 분야 코드만 있어, 표시 이름은 분야 목록에서 찾아 붙입니다.
  const domainNames = useMemo(
    () => new Map((domainsQuery.data ?? []).map((option) => [option.domain, option.name])),
    [domainsQuery.data],
  );

  // 등록한 키워드가 있는 분야만 거르개로 내놓습니다.
  const usedDomains = useMemo(() => [...new Set(keywords.map((keyword) => keyword.domain))], [keywords]);
  // 고른 분야의 마지막 키워드를 빼면 그 칩도 사라지므로, 갇히지 않게 전체로 되돌립니다.
  const activeDomain = usedDomains.includes(selectedDomain) ? selectedDomain : ALL_DOMAINS;
  const visibleKeywords = activeDomain === ALL_DOMAINS
    ? keywords
    : keywords.filter((keyword) => keyword.domain === activeDomain);

  return (
    <PageContainer>
      <div className="mypage-layout">
        <MyPageSidebar profile={profileQuery.data} keywordCount={keywords.length} />

        <div className="mypage-main">
          <div className="mypage-titlebar">
            <h1>관심 키워드</h1>
            <p>등록한 키워드가 트렌드에 오르면 알림을 보내 드립니다</p>
          </div>

          <KeywordSearchBar />

          {interestKeywordsQuery.isError && (
            <ErrorState message="관심 키워드를 불러오지 못했습니다." onRetry={() => interestKeywordsQuery.refetch()} />
          )}
          {interestKeywordsQuery.isLoading && <div className="mypage-loading" aria-label="불러오는 중"><span /><span /><span /></div>}

          {interestKeywordsQuery.isSuccess && (
            <section className="mypage-keywords" aria-label="내 관심 키워드">
              <header className="mypage-keywords-head">
                <h2>내 관심 키워드<span>{keywords.length}개</span></h2>
                {usedDomains.length > 1 && (
                  <div className="mypage-filter">
                    {[ALL_DOMAINS, ...usedDomains].map((domain) => (
                      <button
                        type="button"
                        key={domain}
                        className={`mypage-chip${domain === activeDomain ? ' is-selected' : ''}`}
                        aria-pressed={domain === activeDomain}
                        onClick={() => setSelectedDomain(domain)}
                      >
                        {domain === ALL_DOMAINS ? domain : domainNames.get(domain) ?? domain}
                      </button>
                    ))}
                  </div>
                )}
              </header>

              {keywords.length === 0 && <MyPageEmpty />}
              {keywords.length > 0 && <InterestKeywordList keywords={visibleKeywords} domainNames={domainNames} />}
            </section>
          )}

          {recommendedQuery.isSuccess && <RecommendedKeywords recommendations={recommendedQuery.data} />}
        </div>
      </div>
    </PageContainer>
  );
}
