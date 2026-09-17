import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { Spinner } from '../../components/common/Spinner';
import { showToast } from '../../components/common/toast';
import { getAuthSession } from '../../features/auth/api/authSessionStorage';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';
import { describeAuthError } from '../../features/auth/authErrors';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { useUpdateMyDomains } from '../../features/onboarding/hooks/useUpdateMyDomains';
import { useInterestKeywords } from '../../features/myPage/hooks/useInterestKeywords';
import { useRecommendedKeywords } from '../../features/myPage/hooks/useRecommendedKeywords';
import {
  useDeleteInterestKeyword,
  useRegisterInterestKeyword,
} from '../../features/myPage/hooks/useInterestKeywordMutations';
import { useMyProfile } from '../../features/myPage/hooks/useMyProfile';
import { useKeywordSearch } from '../../features/trend/hooks/useKeywordSearch';
import type { DomainOption } from '../../features/onboarding/types/onboarding';

/**
 * 시안은 분야마다 그림을 답니다. 분야는 서버 enum 이라 여기서 목록을 정하지 않고, 아는 코드에만
 * 그림을 붙이고 모르는 코드는 기본 그림으로 넘깁니다. 분야가 늘어도 화면은 고치지 않아도 됩니다.
 */
const DOMAIN_ICONS: Record<string, string> = {
  DEVELOP: '💻',
  FASHION: '👗',
};
const DOMAIN_ICON_FALLBACK = '🏷️';

/**
 * 시안의 알림 설정 카드입니다. 서버에 알림 설정 API 가 아직 없어 고른 값은 이 화면에만 남습니다.
 * API 가 생기면 enabled 를 그 응답에 이어 붙이면 됩니다.
 */
const NOTIFICATION_OPTIONS = [
  { id: 'surging', icon: '🔥', title: '급상승 알림', desc: '지금 뜨는 트렌드를 가장 빠르게 알려드려요.', tint: '#fef2f2' },
  { id: 'new', icon: '🆕', title: '신규 트렌드 알림', desc: '새롭게 등장한 트렌드를 알려드려요.', tint: '#eef2ff' },
  { id: 'resurging', icon: '📈', title: '재급상승 알림', desc: '다시 주목받는 트렌드를 알려드려요.', tint: '#f0fdf4' },
  { id: 'interest', icon: '🔖', title: '관심 키워드만 받기', desc: '내가 선택한 키워드의 트렌드만 모아보세요.', tint: '#fefce8' },
];

/** 글자를 칠 때마다 보내지 않고, 잠시 멈춘 뒤의 값으로만 찾습니다. */
const SEARCH_DELAY_MS = 250;

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

interface DomainCardProps {
  options: DomainOption[];
  selected: string[];
  disabled: boolean;
  onToggle: (domain: string) => void;
}

function DomainCard({ options, selected, disabled, onToggle }: DomainCardProps) {
  return (
    <section className="onboarding-card">
      <div className="onboarding-card-head">
        <span className="onboarding-card-step" aria-hidden="true">1</span>
        <h2>관심 분야 선택</h2>
        <span className="onboarding-card-note">여러 개 고를 수 있어요.</span>
      </div>
      <p className="onboarding-card-desc">관심 있는 분야를 선택해주세요. (복수 선택 가능)</p>

      <div className="onboarding-domains" role="group" aria-label="관심 분야">
        {options.map((option) => {
          const on = selected.includes(option.domain);
          return (
            <button
              key={option.domain}
              type="button"
              className={`onboarding-domain${on ? ' is-selected' : ''}`}
              role="checkbox"
              aria-checked={on}
              disabled={disabled}
              onClick={() => onToggle(option.domain)}
            >
              <span className="onboarding-domain-icon" aria-hidden="true">
                {DOMAIN_ICONS[option.domain] ?? DOMAIN_ICON_FALLBACK}
              </span>
              {option.name}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function KeywordCard() {
  const keywordsQuery = useInterestKeywords();
  const recommendedQuery = useRecommendedKeywords();
  const register = useRegisterInterestKeyword();
  const remove = useDeleteInterestKeyword();

  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query), SEARCH_DELAY_MS);
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

  const searchQuery = useKeywordSearch(debounced);
  const trimmed = query.trim();
  const searching = trimmed.length > 0 && (searchQuery.isLoading || debounced.trim() !== trimmed);

  const mine = keywordsQuery.data ?? [];
  const mineIds = new Set(mine.map((item) => item.keywordId));
  const results = (searchQuery.data?.items ?? []).filter((item) => !mineIds.has(item.keywordId));
  // 이미 담은 키워드를 다시 권하면 누를 곳이 없어, 추천에서는 빼고 보여 줍니다.
  const recommended = (recommendedQuery.data ?? []).filter((item) => !mineIds.has(item.keywordId)).slice(0, 6);

  const add = (keywordId: number, keyword: string) => {
    register.mutate({ keywordId, keyword });
    setQuery('');
    setOpen(false);
  };

  return (
    <section className="onboarding-card">
      <div className="onboarding-card-head">
        <span className="onboarding-card-step" aria-hidden="true">2</span>
        <h2>관심 키워드 추가</h2>
        <button
          type="button"
          className="onboarding-card-link"
          onClick={() => recommendedQuery.refetch()}
          disabled={recommendedQuery.isFetching}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          다른 추천 키워드 보기
        </button>
      </div>
      <p className="onboarding-card-desc">관심 있는 키워드를 추가해주세요.</p>

      {/* 서버에 있는 키워드만 담을 수 있어, 시안의 '추가' 버튼 대신 찾은 목록에서 고르게 합니다. */}
      <div className="onboarding-search" ref={wrap}>
        <span className="onboarding-search-icon" aria-hidden="true"><SearchIcon /></span>
        <input
          type="text"
          value={query}
          aria-label="키워드 검색"
          placeholder="관심 키워드를 입력해 찾아보세요."
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
        />
        {open && trimmed.length > 0 && (
          <div className="onboarding-search-menu" role="listbox" aria-label="검색 결과">
            {searching && <p className="onboarding-search-none">찾는 중…</p>}
            {!searching && searchQuery.isError && <p className="onboarding-search-none">키워드를 찾지 못했습니다.</p>}
            {!searching && searchQuery.isSuccess && results.length === 0 && (
              <p className="onboarding-search-none">검색어와 맞는 키워드가 없습니다.</p>
            )}
            {!searching && results.map((item) => (
              <button
                type="button"
                className="onboarding-search-row"
                key={item.keywordId}
                onClick={() => add(item.keywordId, item.keyword)}
                disabled={register.isPending}
              >
                <strong>{item.keyword}</strong>
                <small>{item.domain.name}</small>
              </button>
            ))}
          </div>
        )}
      </div>

      {recommended.length > 0 && (
        <div className="onboarding-chips">
          <span className="onboarding-chips-label">추천</span>
          {recommended.map((item) => (
            <button
              type="button"
              className="onboarding-chip"
              key={item.keywordId}
              onClick={() => add(item.keywordId, item.keyword)}
              disabled={register.isPending}
            >
              {item.keyword}
            </button>
          ))}
        </div>
      )}

      <div className="onboarding-chips onboarding-chips--mine">
        {mine.length === 0 && <span className="onboarding-chips-label">아직 담은 키워드가 없습니다.</span>}
        {mine.map((item) => (
          <span className="onboarding-chip is-mine" key={item.interestKeywordId}>
            {item.keyword}
            <button
              type="button"
              aria-label={`${item.keyword} 빼기`}
              onClick={() => remove.mutate({ interestKeywordId: item.interestKeywordId, keyword: item.keyword })}
              disabled={remove.isPending}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </span>
        ))}
      </div>
    </section>
  );
}

interface NotificationCardProps {
  enabled: string[];
  onToggle: (id: string) => void;
}

function NotificationCard({ enabled, onToggle }: NotificationCardProps) {
  return (
    <section className="onboarding-card">
      <div className="onboarding-card-head">
        <span className="onboarding-card-step" aria-hidden="true">3</span>
        <h2>알림 설정</h2>
      </div>
      <p className="onboarding-card-desc">원하는 알림을 선택하면, 중요한 트렌드를 놓치지 않을 수 있어요.</p>

      <div className="onboarding-notifs">
        {NOTIFICATION_OPTIONS.map((option) => {
          const on = enabled.includes(option.id);
          return (
            <button
              key={option.id}
              type="button"
              className={`onboarding-notif${on ? ' is-on' : ''}`}
              role="switch"
              aria-checked={on}
              onClick={() => onToggle(option.id)}
            >
              <span className="onboarding-notif-icon" style={{ background: option.tint }} aria-hidden="true">{option.icon}</span>
              <span className="onboarding-notif-text">
                <strong>{option.title}</strong>
                <small>{option.desc}</small>
              </span>
              <span className="onboarding-notif-switch" aria-hidden="true"><i /></span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function OnboardingPage() {
  const session = useAuthSession();
  const navigate = useNavigate();
  const profileQuery = useMyProfile();
  const domainsQuery = useDomains();
  const myDomainsQuery = useMyDomains(Boolean(session));
  const updateMutation = useUpdateMyDomains();
  const keywordsQuery = useInterestKeywords();

  const [selected, setSelected] = useState<string[]>([]);
  const [formError, setFormError] = useState<string>();
  // 고른 분야를 한 번만 켜 둡니다. 이후에는 사용자가 누른 것이 이깁니다.
  const [seeded, setSeeded] = useState(false);
  // 알림은 저장할 곳이 없어 화면 안에서만 삽니다. 시안의 기본값대로 앞의 셋을 켜 둡니다.
  const [notifications, setNotifications] = useState(['surging', 'new', 'resurging']);

  // 고친 뒤 다시 들어오는 경우가 있어, 이미 고른 분야를 켜 둔 채로 시작합니다.
  useEffect(() => {
    if (seeded || !myDomainsQuery.data) return;
    setSelected(myDomainsQuery.data.map((option) => option.domain));
    setSeeded(true);
  }, [myDomainsQuery.data, seeded]);

  const toggle = (domain: string) => {
    setFormError(undefined);
    setSelected((current) => (current.includes(domain)
      ? current.filter((value) => value !== domain)
      : [...current, domain]));
  };

  const toggleNotification = (id: string) => {
    setNotifications((current) => (current.includes(id)
      ? current.filter((value) => value !== id)
      : [...current, id]));
  };

  const submit = async () => {
    if (selected.length === 0) {
      setFormError('관심 분야는 최소 1개 이상 선택해야 합니다.');
      return;
    }
    setFormError(undefined);

    try {
      await updateMutation.mutateAsync(selected);
      showToast({ message: '관심 분야를 저장했습니다.', type: 'success' });
      // 분야를 막 고른 사람이 볼 것은 소개 화면이 아니라 그 분야가 반영된 대시보드입니다.
      navigate('/dashboard', { replace: true });
    } catch (error) {
      setFormError(describeAuthError(error, '관심 분야를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.'));
    }
  };

  // 로그인해야 고른 분야를 저장할 수 있습니다.
  if (!getAuthSession()) return <Navigate to="/login" state={{ from: '/onboarding' }} replace />;

  const options = domainsQuery.data ?? [];
  const loading = domainsQuery.isLoading || (myDomainsQuery.isLoading && !myDomainsQuery.isError);
  const keywordCount = keywordsQuery.data?.length ?? 0;

  return (
    <div className="trendin-ui onboarding-page">
      <header className="onboarding-header">
        <span className="onboarding-brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" fill="#4F46E5" stroke="#4F46E5" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          TrendIn
        </span>
        <span className="onboarding-who">
          {profileQuery.data && <span>{profileQuery.data.nickname}님</span>}
          <span className="onboarding-avatar" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round">
              <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </span>
        </span>
      </header>

      <div className="onboarding-main">
        <div className="onboarding-hero">
          <p className="onboarding-eyebrow">PERSONALIZE YOUR TREND JOURNEY</p>
          <h1>관심 설정으로 나만의 <span>TrendIn</span>을 만들어보세요.</h1>
          <p className="onboarding-lead">관심 분야와 키워드를 설정하면, 더 정확하고 흥미로운 트렌드를 추천해드려요.</p>
        </div>

        {/* 세 단계가 한 화면에 다 있어 누를 곳은 아니고, 어디까지 채웠는지만 짚어 줍니다. */}
        <ol className="onboarding-steps" aria-hidden="true">
          <li className={selected.length > 0 ? 'is-done' : 'is-current'}>
            <span className="onboarding-step-mark">1</span>
            <span className="onboarding-step-text"><strong>관심 분야</strong><small>분야를 선택해주세요</small></span>
          </li>
          <li className={keywordCount > 0 ? 'is-done' : 'is-current'}>
            <span className="onboarding-step-mark">2</span>
            <span className="onboarding-step-text"><strong>키워드 선택</strong><small>키워드를 추가해주세요</small></span>
          </li>
          <li className="is-idle">
            <span className="onboarding-step-mark">3</span>
            <span className="onboarding-step-text"><strong>알림 설정</strong><small>알림 옵션을 설정해주세요</small></span>
          </li>
        </ol>

        <div className="onboarding-cards">
          {domainsQuery.isError && (
            <ErrorState message="분야 목록을 불러오지 못했습니다." onRetry={() => domainsQuery.refetch()} />
          )}

          {!domainsQuery.isError && loading && (
            <div className="onboarding-loading" aria-label="불러오는 중"><Spinner /></div>
          )}

          {!domainsQuery.isError && !loading && (
            <>
              <DomainCard
                options={options}
                selected={selected}
                disabled={updateMutation.isPending}
                onToggle={toggle}
              />
              <KeywordCard />
              <NotificationCard enabled={notifications} onToggle={toggleNotification} />

              {formError && <p className="onboarding-alert" role="alert">{formError}</p>}

              <div className="onboarding-actions">
                <button
                  type="button"
                  className="onboarding-later"
                  disabled={updateMutation.isPending}
                  onClick={() => navigate('/dashboard', { replace: true })}
                >
                  나중에 설정하기
                </button>
                <button type="button" className="onboarding-done" disabled={updateMutation.isPending} onClick={submit}>
                  {updateMutation.isPending && <Spinner size="small" />}
                  {updateMutation.isPending ? '저장하는 중…' : '맞춤 설정 완료'}
                  {!updateMutation.isPending && (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                      <path d="M5 12h14M13 6l6 6-6 6" />
                    </svg>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
