import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { showToast } from '../../components/common/toast';
import { getApiErrorMessage } from '../../api/apiResponse';
import { validateNickname } from '../../features/auth/validation';
import { MyPageCard, MyPageCrumb, MyPageScreen } from '../../features/myPage/components/MyPageShell';
import { useMyProfile } from '../../features/myPage/hooks/useMyProfile';
import { useUpdateMyProfile } from '../../features/myPage/hooks/useUpdateMyProfile';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { useUpdateMyDomains } from '../../features/onboarding/hooks/useUpdateMyDomains';

/** 이메일을 모르는 소셜 계정도 있어서, 머리글자를 못 뽑으면 기본 글자를 씁니다. */
function initialOf(nickname: string, email: string) {
  return (nickname.trim()[0] ?? email.trim()[0] ?? 'T').toUpperCase();
}

const DISPLAY_DOMAINS = [
  { domain: 'GAME', name: '게임', icon: '🎮' },
  { domain: 'DEVELOP', name: '개발', icon: '💻' },
  { domain: 'FASHION', name: '패션', icon: '👗' },
  { domain: 'BEAUTY', name: '뷰티', icon: '💄' },
  { domain: 'MUSIC', name: '음악', icon: '🎵' },
  { domain: 'TRAVEL', name: '여행', icon: '✈️' },
  { domain: 'CONTENT', name: '콘텐츠', icon: '🎬' },
  { domain: 'FINANCE', name: '금융', icon: '💰' },
] as const;

export function ProfileEditPage() {
  const navigate = useNavigate();
  const profileQuery = useMyProfile();
  const domainsQuery = useDomains();
  const myDomainsQuery = useMyDomains(true);
  const updateProfile = useUpdateMyProfile();
  const updateDomains = useUpdateMyDomains();

  const [nickname, setNickname] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [formError, setFormError] = useState<string>();
  // 받아 온 값으로 한 번만 채웁니다. 이후에는 고치던 내용이 이깁니다.
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (seeded || !profileQuery.data || !myDomainsQuery.data) return;
    setNickname(profileQuery.data.nickname);
    setSelected(myDomainsQuery.data.map((option) => option.domain));
    setSeeded(true);
  }, [myDomainsQuery.data, profileQuery.data, seeded]);

  const profile = profileQuery.data;
  const savedDomains = myDomainsQuery.data?.map((option) => option.domain) ?? [];
  const nicknameChanged = Boolean(profile) && nickname.trim() !== profile?.nickname;
  const domainsChanged = [...selected].sort().join() !== [...savedDomains].sort().join();
  const saving = updateProfile.isPending || updateDomains.isPending;

  const toggleDomain = (domain: string) => {
    setFormError(undefined);
    setSelected((current) => (current.includes(domain)
      ? current.filter((value) => value !== domain)
      : [...current, domain]));
  };

  /*
   * 닉네임과 분야는 서버가 다른 경로로 받습니다. 바뀐 것만 보내서, 한쪽만 고쳤을 때
   * 다른 쪽까지 굳이 건드리지 않습니다.
   */
  const save = async () => {
    const invalid = validateNickname(nickname);
    if (invalid) {
      setFormError(invalid);
      return;
    }
    if (selected.length === 0) {
      return;
    }
    setFormError(undefined);

    try {
      if (nicknameChanged) await updateProfile.mutateAsync(nickname.trim());
      if (domainsChanged) await updateDomains.mutateAsync(selected);
      showToast({ message: '프로필을 저장했습니다.', type: 'success' });
      navigate('/mypage');
    } catch (error) {
      setFormError(getApiErrorMessage(error) ?? '프로필을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.');
    }
  };

  return (
    <MyPageScreen width="sm">
      <MyPageCrumb current="프로필 편집" />
      <div className="mypage-head trendin-page-heading">
        <h1>프로필 편집</h1>
      </div>

      {profileQuery.isError && (
        <div className="trendin-state is-error" role="alert">
          <p>프로필을 불러오지 못했습니다.</p>
          <button type="button" onClick={() => profileQuery.refetch()}>다시 시도</button>
        </div>
      )}

      <section className="mypage-card mypage-avatar-card">
        <span className="mypage-avatar" aria-hidden="true">
          {profile ? initialOf(profile.nickname, profile.email) : 'T'}
        </span>
        <div>
          <p className="mypage-row-title">프로필 사진</p>
          {/* 사진을 올려 둘 곳이 서버에 없습니다. 고를 수 있는 것처럼 두지 않고 잠가 둡니다. */}
          <p className="mypage-row-desc">닉네임 첫 글자로 그립니다. 사진 올리기는 아직 준비 중입니다.</p>
        </div>
      </section>

      <MyPageCard title="기본 정보" tone="indigo">
        <div className="mypage-fields">
          <label className="mypage-field">
            <span>이름 <em>*</em></span>
            <input
              type="text"
              value={nickname}
              maxLength={30}
              placeholder="2자 이상 30자 이하"
              disabled={!profile || saving}
              onChange={(event) => { setNickname(event.target.value); setFormError(undefined); }}
            />
          </label>

          <label className="mypage-field">
            <span>이메일</span>
            <input type="email" value={profile?.email ?? ''} disabled readOnly />
            <small>이메일은 변경할 수 없습니다.</small>
          </label>
        </div>
      </MyPageCard>

      <MyPageCard title="관심 분야" tone="emerald">
        <p className="mypage-card-lead">관심 분야를 설정하면 그 분야의 트렌드를 먼저 받아 볼 수 있습니다.</p>

        {domainsQuery.isLoading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}
        {domainsQuery.isError && (
          <div className="trendin-state is-error" role="alert">
            <p>분야 목록을 불러오지 못했습니다.</p>
            <button type="button" onClick={() => domainsQuery.refetch()}>다시 시도</button>
          </div>
        )}

        {domainsQuery.isSuccess && (
          <>
            <div className="mypage-chips">
              {DISPLAY_DOMAINS.map((option) => (
                <button
                  key={option.domain}
                  type="button"
                  aria-pressed={selected.includes(option.domain)}
                  className={`mypage-chip${selected.includes(option.domain) ? ' is-on' : ''}${option.domain !== 'FASHION' ? ' is-unavailable' : ''}`}
                  disabled={saving || option.domain !== 'FASHION' || !domainsQuery.data.some((domain) => domain.domain === option.domain)}
                  onClick={() => toggleDomain(option.domain)}
                >
                  <span aria-hidden="true">{option.icon}</span> {option.name}
                </button>
              ))}
            </div>
            {seeded && selected.length === 0 && (
              <p className="mypage-error" role="alert">관심 분야는 최소 1개 이상 선택해야 합니다.</p>
            )}
          </>
        )}
      </MyPageCard>

      {formError && <p className="mypage-error" role="alert">{formError}</p>}

      <div className="mypage-actions">
        <Link className="mypage-btn mypage-btn--ghost" to="/mypage">취소</Link>
        <button
          type="button"
          className="mypage-btn mypage-btn--primary"
          disabled={!profile || saving || selected.length === 0 || (!nicknameChanged && !domainsChanged)}
          onClick={() => void save()}
        >
          {saving ? '저장 중…' : '변경사항 저장'}
        </button>
      </div>
    </MyPageScreen>
  );
}
