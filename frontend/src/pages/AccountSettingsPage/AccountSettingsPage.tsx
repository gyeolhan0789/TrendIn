import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { showToast } from '../../components/common/toast';
import { MyPageCard, MyPageCrumb, MyPageScreen } from '../../features/myPage/components/MyPageShell';
import { DownloadIcon, UserIcon, WarnIcon } from '../../features/myPage/components/myPageIcons';
import { useInterestKeywords } from '../../features/myPage/hooks/useInterestKeywords';
import { useMyProfile } from '../../features/myPage/hooks/useMyProfile';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { useSavedTrends } from '../../features/savedTrend/hooks/useSavedTrends';
import { useLogout } from '../../features/auth/hooks/useLogout';
import { downloadFile, toCsv, today } from '../../utils/download';

/** 준비 중인 자리에 다는 표. 눌러도 되는 것처럼 보이지 않게 단추 대신 이 표를 세웁니다. */
function SoonBadge() {
  return <span className="mypage-badge">준비 중</span>;
}

export function AccountSettingsPage() {
  const navigate = useNavigate();
  const profileQuery = useMyProfile();
  const domainsQuery = useMyDomains(true);
  const keywordsQuery = useInterestKeywords();
  const savedTrendsQuery = useSavedTrends();
  const logoutMutation = useLogout();

  const profile = profileQuery.data;
  const keywords = useMemo(() => keywordsQuery.data ?? [], [keywordsQuery.data]);
  const savedTrends = useMemo(() => savedTrendsQuery.data?.trends ?? [], [savedTrendsQuery.data]);
  // 관심 키워드는 분야 코드만 들고 있어, 표시 이름은 내가 고른 분야 목록에서 찾아 붙입니다.
  const domainNames = useMemo(
    () => new Map((domainsQuery.data ?? []).map((option) => [option.domain, option.name])),
    [domainsQuery.data],
  );

  const exportKeywords = () => {
    downloadFile(
      `trendin-관심키워드-${today()}.csv`,
      toCsv(['키워드', '분야'], keywords.map((item) => [item.keyword, domainNames.get(item.domain) ?? item.domain])),
      'text/csv',
    );
    showToast({ message: '관심 키워드를 내려받았습니다.', type: 'success' });
  };

  const exportSavedTrends = () => {
    downloadFile(
      `trendin-저장된트렌드-${today()}.json`,
      JSON.stringify(savedTrends, null, 2),
      'application/json',
    );
    showToast({ message: '저장된 트렌드를 내려받았습니다.', type: 'success' });
  };

  const signOut = async () => {
    await logoutMutation.mutateAsync();
    navigate('/', { replace: true });
  };

  return (
    <MyPageScreen width="md">
      <MyPageCrumb current="계정 설정" />
      <div className="mypage-head trendin-page-heading">
        <h1>계정 설정</h1>
      </div>

      <MyPageCard
        title="개인정보"
        tone="indigo"
        icon={<UserIcon />}
        action={<Link className="mypage-card-link" to="/mypage/profile">수정 →</Link>}
      >
        <dl className="mypage-facts">
          <div>
            <dt>이름</dt>
            <dd>{profile?.nickname ?? '—'}</dd>
          </div>
          <div>
            <dt>이메일</dt>
            {/* 소셜로 들어온 계정은 이메일을 모를 수 있습니다. 빈 칸 대신 그 사정을 적습니다. */}
            <dd>{profile?.email || (profile ? '연결된 소셜 계정' : '—')}</dd>
          </div>
          <div>
            <dt>관심 분야</dt>
            <dd>{domainsQuery.data?.map((option) => option.name).join(', ') || '—'}</dd>
          </div>
        </dl>
      </MyPageCard>

      <MyPageCard title="데이터 내보내기" tone="blue" icon={<DownloadIcon />}>
        {/* 서버에 내보내기 API는 없지만, 이 두 가지는 화면이 이미 들고 있어 그 자리에서 파일로 만듭니다. */}
        <div className="mypage-exports">
          <div className="mypage-export">
            <p className="mypage-row-title">관심 키워드 목록</p>
            <p className="mypage-row-desc">{keywords.length}개 키워드 · CSV 형식</p>
            <button type="button" disabled={keywords.length === 0} onClick={exportKeywords}>다운로드</button>
          </div>
          <div className="mypage-export">
            <p className="mypage-row-title">저장된 트렌드</p>
            <p className="mypage-row-desc">{savedTrends.length}개 트렌드 · JSON 형식</p>
            <button type="button" disabled={savedTrends.length === 0} onClick={exportSavedTrends}>다운로드</button>
          </div>
        </div>
      </MyPageCard>

      <MyPageCard title="위험 영역" tone="rose" icon={<WarnIcon />} danger>
        <div className="mypage-danger">
          <div className="mypage-row-text">
            <p className="mypage-row-title">계정 삭제</p>
            <p className="mypage-row-desc">모든 자료가 영구히 지워집니다. 되돌릴 수 없습니다.</p>
          </div>
          {/* 계정을 지우는 API가 없습니다. 눌리는 단추를 두면 눌러 놓고 지워진 줄 압니다. */}
          <SoonBadge />
        </div>
      </MyPageCard>

      <div className="mypage-actions mypage-actions--split">
        <button
          type="button"
          className="mypage-btn mypage-btn--ghost"
          disabled={logoutMutation.isPending}
          onClick={() => void signOut()}
        >
          {logoutMutation.isPending ? '로그아웃 중…' : '로그아웃'}
        </button>
        <Link className="mypage-btn mypage-btn--ghost" to="/mypage">마이페이지로</Link>
      </div>
    </MyPageScreen>
  );
}
