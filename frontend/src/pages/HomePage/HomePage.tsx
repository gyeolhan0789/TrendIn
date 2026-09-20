import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import heroWave from '../../assets/flowing-wave.webp';
import { CylinderCarousel } from '../../components/common/CylinderCarousel';
import { FilterSelect } from '../../components/common/FilterSelect';
import { useInterestKeywords } from '../../features/myPage/hooks/useInterestKeywords';
import { useRegisterInterestKeyword } from '../../features/myPage/hooks/useInterestKeywordMutations';
import { useRecommendedKeywords } from '../../features/myPage/hooks/useRecommendedKeywords';
import type { RecommendedKeyword } from '../../features/myPage/types/myPage';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { TOP_COUNT, TrendRankBoard } from '../../features/trend/components/TrendRankBoard';
import { useTrends } from '../../features/trend/hooks/useTrends';
import { ANALYSIS_PERIODS, parsePeriod, resolveDomainCode } from '../../constants/filterCodes';
import type { PeriodCode } from '../../constants/filterCodes';
import { TREND_TYPES } from '../../features/trend/types/trend';
import type { TrendAnalysisWindow, TrendType } from '../../features/trend/types/trend';

const periodLabels: Record<PeriodCode, string> = {
  '24H': '최근 24시간',
  '7D': '최근 7일',
  '30D': '최근 30일',
};

/** 캐러셀의 점에 붙는 짧은 이름입니다. 판 안의 제목은 '인기 트렌드'처럼 길게 둡니다. */
/** 빠른 탐색 칸이 좁아 추천은 여덟 개까지만 세웁니다. */
const RECOMMEND_COUNT = 8;

const typeLabels: Record<TrendType, string> = {
  CURRENT: '인기',
  NEW: '신규',
  RISING: '급상승',
};

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
  /*
   * 고를 수 있는 분야 전체가 아니라 내가 고른 분야만 받습니다. 이 화면은 내 관심사를 보는 자리라,
   * 고르지 않은 분야의 트렌드까지 내밀면 거르개가 아니라 남의 목록이 됩니다.
   *
   * 주소에 고르지 않은 분야가 적혀 있어도 resolveDomainCode 가 내 첫 분야로 되돌립니다.
   */
  const domainsQuery = useMyDomains(true);
  const domains = useMemo(() => domainsQuery.data ?? [], [domainsQuery.data]);
  // 받아 왔는데 비어 있으면 아직 아무 분야도 고르지 않은 것입니다. 받는 중인 것과 갈라야 합니다.
  const noChosenDomain = domainsQuery.isSuccess && domains.length === 0;

  /*
   * 고를 것이 없을 때 칸을 비워 두면 무엇을 기다리는지 알 수 없습니다. 잠긴 칸에 사정을 적되,
   * 아직 못 받은 것과 고른 적이 없는 것은 할 일이 달라서 문구를 가릅니다.
   */
  const categoryOptions = useMemo(() => {
    if (domains.length > 0) return domains.map((option) => ({ value: option.domain, label: option.name }));
    if (domainsQuery.isError) return [{ value: '', label: '불러오지 못함' }];
    return [{ value: '', label: noChosenDomain ? '고른 분야 없음' : '불러오는 중…' }];
  }, [domains, domainsQuery.isError, noChosenDomain]);

  const period = parsePeriod(searchParams.get('period'));
  const rawType = searchParams.get('status')?.toUpperCase() ?? '';
  const type: TrendType = (TREND_TYPES as readonly string[]).includes(rawType) ? (rawType as TrendType) : 'CURRENT';

  // 분야 목록을 받기 전에는 고를 분야가 없어 조회를 멈춰 둡니다.
  const domain = resolveDomainCode(searchParams.get('category'), domains);

  /*
   * 집계 구간은 지금 보는 판의 것을 씁니다. 순위판이 처음 부르는 조회와 조건이 같아 캐시를
   * 함께 쓰므로, 이 줄 때문에 서버를 한 번 더 부르지는 않습니다.
   */
  const shownQuery = useTrends(domain ? { domain, type, period, page: 0, size: TOP_COUNT } : undefined);
  const windowLabel = describeWindow(shownQuery.data?.analysisWindow);
  const recommendedQuery = useRecommendedKeywords();

  /*
   * 서버는 이미 담은 키워드를 추천에서 빼 줍니다. 그대로 그리면 담는 순간 꼬리표가 사라져,
   * 담았다는 표시를 볼 새가 없고 뒤 꼬리표들이 앞으로 밀려 눈이 따라가지 못합니다.
   *
   * 그래서 처음 받은 목록을 붙잡아 둡니다. 자리는 그대로 두고 아래 registeredIds 가 체크로
   * 뒤집습니다. 새 추천은 화면을 다시 열 때 받습니다.
   */
  const [recommended, setRecommended] = useState<RecommendedKeyword[]>([]);

  useEffect(() => {
    const fresh = recommendedQuery.data;
    if (!fresh || fresh.length === 0 || recommended.length > 0) return;
    // 패널이 좁아 여덟 개에서 끊습니다. 연관도가 높은 순서로 오므로 앞에서 자릅니다.
    setRecommended(fresh.slice(0, RECOMMEND_COUNT));
  }, [recommended.length, recommendedQuery.data]);

  /*
   * 이미 담은 키워드인지는 꼬리표마다 목록을 훑지 않고 여기서 한 번만 추려 둡니다.
   * 등록이 끝나면 관심 키워드 목록이 다시 받아져 이 집합도 따라 바뀌고, 꼬리표가 체크 표시로 넘어갑니다.
   */
  const interestKeywordsQuery = useInterestKeywords();
  const registerMutation = useRegisterInterestKeyword();
  const registeredIds = useMemo(
    () => new Set((interestKeywordsQuery.data ?? []).map((item) => item.keywordId)),
    [interestKeywordsQuery.data],
  );

  const updateParams = (updates: Record<string, string | undefined>, replace = false) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === undefined) next.delete(key);
      else next.set(key, value);
    });
    setSearchParams(next, { replace });
  };

  /* 캐러셀 자리는 주소창의 status 와 한 몸입니다. 돌릴 때마다 뒤로가기가 쌓이지 않게 바꿔치기합니다. */
  const slides = TREND_TYPES.map((code) => ({
    key: code,
    label: typeLabels[code],
    node: <TrendRankBoard type={code} domain={domain} period={period} />,
  }));

  return (
    <div className="explore-page">
      <section className="explore-hero trendin-page-heading">
        <div>
          <p className="explore-hero-eyebrow trendin-page-eyebrow">트렌드를 더 빠르게, 더 깊이</p>
          <h1>트렌드 탐색</h1>
          <p className="explore-hero-lead trendin-page-lead">{windowLabel ?? '인기·신규·급상승 트렌드를 한눈에 확인하세요.'}</p>
        </div>
        <div className="explore-hero-visual">
          <img src={heroWave} alt="" />
          <div className="explore-hero-note">
            <p>지금 이 순간에도<br />새로운 트렌드가 만들어지고 있어요.</p>
          </div>
        </div>
      </section>

      <section className="explore-searchbar">
        <div className="explore-filters">
          <FilterSelect
            label="기간"
            value={period}
            options={ANALYSIS_PERIODS.map((code) => ({ value: code, label: periodLabels[code] }))}
            onChange={(value) => updateParams({ period: value })}
          />

          <FilterSelect
            label="카테고리"
            value={domain ?? ''}
            options={categoryOptions}
            onChange={(value) => updateParams({ category: value })}
            disabled={domains.length === 0}
          />
        </div>
      </section>

      <section className="explore-main">
        {domainsQuery.isError && (
          <div className="trendin-state is-error" role="alert">
            <p>분야를 불러오지 못했습니다.</p>
            <button type="button" onClick={() => void domainsQuery.refetch()}>다시 시도</button>
          </div>
        )}
        {/*
          * 고른 분야가 없으면 보여 줄 판이 없습니다. '집계된 트렌드가 없다'고 하면 서버 탓처럼
          * 읽히므로, 무엇이 비었고 어디서 채우는지를 짚어 줍니다.
          */}
        {noChosenDomain && (
          <div className="trendin-state" role="status">
            <p>아직 고른 관심 분야가 없습니다.</p>
            <Link to="/mypage/profile">관심 분야 고르러 가기</Link>
          </div>
        )}
        {!domainsQuery.isError && !noChosenDomain && (
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
          <div className="explore-panel-head"><SearchIcon /><span>함께 떠오르는 키워드</span></div>
          <p className="explore-panel-lead">내 관심 키워드와 함께 언급되는 말입니다. 눌러서 관심 키워드로 담아 보세요.</p>
          <div className="explore-quick">
            {recommended.map((item) => {
              const registered = registeredIds.has(item.keywordId);
              const pending = registerMutation.isPending && registerMutation.variables?.keywordId === item.keywordId;
              return (
                <button
                  type="button"
                  key={item.keywordId}
                  className={registered ? 'is-registered' : undefined}
                  /* 담았는지 아직 모르는 동안 누르면 이미 담은 것을 또 보내게 됩니다. */
                  disabled={registered || pending || !interestKeywordsQuery.isSuccess}
                  aria-label={registered ? `${item.keyword} 관심 키워드에 등록됨` : `${item.keyword} 관심 키워드로 등록`}
                  title={registered ? '이미 등록한 관심 키워드' : '관심 키워드로 등록'}
                  onClick={() => registerMutation.mutate({ keywordId: item.keywordId, keyword: item.keyword })}
                >
                  {item.keyword}
                  <span aria-hidden="true">{registered ? '✓' : '＋'}</span>
                </button>
              );
            })}
            {/* 추천은 내 관심 키워드에 기대므로, 하나도 등록하지 않았으면 서버가 빈 목록을 줍니다. */}
            {recommendedQuery.isSuccess && recommendedQuery.data.length === 0 && (
              <span className="explore-panel-lead">관심 키워드를 등록하면 그와 가까운 말을 모아 드립니다.</span>
            )}
            {recommendedQuery.isLoading && <span className="explore-panel-lead">불러오는 중…</span>}
            {recommendedQuery.isError && <span className="explore-panel-lead">추천 키워드를 불러오지 못했습니다.</span>}
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
