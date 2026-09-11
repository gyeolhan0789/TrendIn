import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { PageContainer } from '../../components/layout/PageContainer';
import { showToast } from '../../components/common/toast';
import { InterestKeywordList } from '../../features/myPage/components/InterestKeywordList';
import { KeywordSearchBar } from '../../features/myPage/components/KeywordSearchBar';
import { MyPageSidebar } from '../../features/myPage/components/MyPageSidebar';
import { RecommendedKeywords } from '../../features/myPage/components/RecommendedKeywords';
import { useInterestKeywords } from '../../features/myPage/hooks/useInterestKeywords';
import { useKeywordCatalog } from '../../features/myPage/hooks/useKeywordCatalog';
import { useMyProfile } from '../../features/myPage/hooks/useMyProfile';
import { recommendKeywords } from '../../features/myPage/recommendKeywords';
import type { InterestKeywordView } from '../../features/myPage/types/myPage';
import { useSavedBoards } from '../../features/savedTrend/hooks/useSavedBoards';

const allCategories = '전체';

function MyPageEmpty() {
  return (
    <div className="mypage-empty">
      <p>아직 등록한 관심 키워드가 없습니다.</p>
      <h2>위 검색창에서 키워드를 찾거나, 없는 말은 직접 입력해 등록할 수 있습니다.</h2>
      <Link className="mypage-empty-action" to="/">대시보드에서 키워드 둘러보기<span aria-hidden="true">→</span></Link>
    </div>
  );
}

export function MyPage() {
  const profileQuery = useMyProfile();
  const catalogQuery = useKeywordCatalog();
  const { boards } = useSavedBoards();
  const { keywords, addKeyword, removeKeyword, setAlerts, moveKeyword, shiftKeyword } = useInterestKeywords();
  const [category, setCategory] = useState(allCategories);

  const catalog = useMemo(() => catalogQuery.data ?? [], [catalogQuery.data]);

  const views = useMemo<InterestKeywordView[]>(() => keywords.map((keyword) => {
    const trend = catalog.find((item) => item.trendId === keyword.trendId);
    return {
      ...keyword,
      trend,
      category: trend?.category,
      alertCount: Number(keyword.alerts.trend) + Number(keyword.alerts.weekly),
    };
  }), [catalog, keywords]);

  // 직접 입력한 키워드는 카테고리가 없어 '전체'에서만 보입니다.
  const categories = useMemo(() => [...new Set(views.map((view) => view.category).filter((value): value is string => Boolean(value)))], [views]);
  // 고른 카테고리의 마지막 키워드를 지우면 그 칩도 사라지므로, 갇히지 않게 전체로 되돌립니다.
  const activeCategory = categories.includes(category) ? category : allCategories;
  const visibleViews = activeCategory === allCategories ? views : views.filter((view) => view.category === activeCategory);

  const alertTotal = views.reduce((total, view) => total + view.alertCount, 0);
  const recommendations = useMemo(() => recommendKeywords(catalog, keywords), [catalog, keywords]);

  const registeredTrendIds = useMemo(() => new Set(keywords.map((keyword) => keyword.trendId).filter((id): id is string => Boolean(id))), [keywords]);
  const registeredKeywords = useMemo(() => new Set(keywords.map((keyword) => keyword.keyword)), [keywords]);

  const register = (input: { keyword: string; trendId?: string }) => {
    const result = addKeyword(input);
    if (!result) return;
    showToast({
      message: result.added
        ? `${result.keyword.keyword}을(를) 관심 키워드에 등록했습니다.`
        : `${result.keyword.keyword}은(는) 이미 등록한 키워드입니다.`,
      type: 'success',
    });
  };

  const unregister = (keywordId: string) => {
    const target = keywords.find((keyword) => keyword.keywordId === keywordId);
    removeKeyword(keywordId);
    showToast({ message: `${target?.keyword ?? '키워드'}을(를) 관심 키워드에서 뺐습니다.`, type: 'success' });
  };

  return (
    <PageContainer>
      <div className="mypage-layout">
        <MyPageSidebar
          profile={profileQuery.data}
          keywordCount={keywords.length}
          boardCount={boards.length}
          alertCount={alertTotal}
        />

        <div className="mypage-main">
          <div className="mypage-titlebar">
            <h1>관심 키워드</h1>
            <p>등록한 키워드의 트렌드를 추적하고 알림을 받으세요</p>
          </div>

          {catalogQuery.isError && <ErrorState message="키워드 목록을 불러오지 못했습니다." onRetry={() => catalogQuery.refetch()} />}

          {!catalogQuery.isError && (
            <>
              <KeywordSearchBar
                catalog={catalog}
                registeredTrendIds={registeredTrendIds}
                registeredKeywords={registeredKeywords}
                onAdd={register}
              />

              {catalogQuery.isLoading && <div className="mypage-loading" aria-label="불러오는 중"><span /><span /><span /></div>}

              {!catalogQuery.isLoading && (
                <section className="mypage-keywords" aria-label="내 관심 키워드">
                  <header className="mypage-keywords-head">
                    <h2>내 관심 키워드<span>{keywords.length}개</span></h2>
                    {categories.length > 0 && (
                      <div className="mypage-filter">
                        {[allCategories, ...categories].map((name) => (
                          <button
                            type="button"
                            key={name}
                            className={`mypage-chip${name === activeCategory ? ' is-selected' : ''}`}
                            aria-pressed={name === activeCategory}
                            onClick={() => setCategory(name)}
                          >
                            {name}
                          </button>
                        ))}
                      </div>
                    )}
                  </header>

                  {keywords.length === 0 && <MyPageEmpty />}
                  {keywords.length > 0 && visibleViews.length === 0 && <p className="mypage-filter-empty">이 카테고리에 등록한 키워드가 없습니다.</p>}
                  {visibleViews.length > 0 && (
                    <InterestKeywordList
                      views={visibleViews}
                      totalCount={keywords.length}
                      indexOf={(keywordId) => keywords.findIndex((keyword) => keyword.keywordId === keywordId)}
                      onAlertsChange={setAlerts}
                      onMove={moveKeyword}
                      onShift={shiftKeyword}
                      onRemove={unregister}
                    />
                  )}
                </section>
              )}

              {!catalogQuery.isLoading && <RecommendedKeywords recommendations={recommendations} />}
            </>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
