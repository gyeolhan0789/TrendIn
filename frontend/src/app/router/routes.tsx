import { Route } from 'react-router-dom';
import { AccountSettingsPage } from '../../pages/AccountSettingsPage/AccountSettingsPage';
import { GlobalTrendsPage } from '../../pages/GlobalTrendsPage/GlobalTrendsPage';
import { HomePage } from '../../pages/HomePage/HomePage';
import { KeywordsPage } from '../../pages/KeywordsPage/KeywordsPage';
import { LandingPage } from '../../pages/LandingPage/LandingPage';
import { LoginPage } from '../../pages/LoginPage/LoginPage';
import { MyPage } from '../../pages/MyPage/MyPage';
import { NotificationSettingsPage } from '../../pages/NotificationSettingsPage/NotificationSettingsPage';
import { OAuthCallbackPage } from '../../pages/OAuthCallbackPage/OAuthCallbackPage';
import { OnboardingPage } from '../../pages/OnboardingPage/OnboardingPage';
import { PasswordResetPage } from '../../pages/PasswordResetPage/PasswordResetPage';
import { ProfileEditPage } from '../../pages/ProfileEditPage/ProfileEditPage';
import { RecentActivityPage } from '../../pages/RecentActivityPage/RecentActivityPage';

import { SavedTrendPage } from '../../pages/SavedTrendPage/SavedTrendPage';
import { SignUpPage } from '../../pages/SignUpPage/SignUpPage';
import { TrendDetailPage } from '../../pages/TrendDetailPage/TrendDetailPage';

/*
 * 랜딩은 로그인 전에도 열리는 소개 화면이라 가드 밖에 둡니다. 다만 트렌드 조회는
 * 토큰을 요구하므로, 로그인 전에는 화면이 알아서 자료 없는 모양으로 내려앉습니다.
 */
export const landingRoutes = <Route path="/" element={<LandingPage />} />;

/* 새 시안으로 다시 그렸고, 자료를 받으려면 로그인해야 하는 화면들. */
export const siteRoutes = (
  <>
    <Route path="/dashboard" element={<HomePage />} />
    <Route path="/keywords" element={<KeywordsPage />} />
    <Route path="/mypage" element={<MyPage />} />
    <Route path="/mypage/profile" element={<ProfileEditPage />} />
    <Route path="/mypage/settings" element={<AccountSettingsPage />} />
    <Route path="/mypage/activity" element={<RecentActivityPage />} />
    <Route path="/mypage/notifications" element={<NotificationSettingsPage />} />
    <Route path="/saved" element={<SavedTrendPage />} />
  </>
);

/*
 * 지도가 창을 가득 채우는 화면. 머리말만 얹고 푸터는 두지 않아, 스크롤 없이 한 화면에서 끝납니다.
 */
export const stageRoutes = <Route path="/global" element={<GlobalTrendsPage />} />;

/* 아직 옛 모양인 화면들. 각자 시안이 나오면 위로 옮겨 갑니다. */
export const appRoutes = (
  <>
    <Route path="/trends/:trendId" element={<TrendDetailPage />} />
  </>
);

/*
 * 인증 화면은 공용 레이아웃 밖에 둡니다. 아직 로그인하지 않은 사람에게
 * 대시보드 내비게이션과 담기 패널까지 보여 줄 이유가 없습니다.
 *
 * 콜백은 API가 아니라 화면이라서 경로를 /auth 밖에 둡니다. 배포에서 /auth 아래는
 * 백엔드로 넘어가므로, 그 밑에 두면 화면 대신 백엔드 응답이 돌아옵니다.
 */
export const authRoutes = (
  <>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/signup" element={<SignUpPage />} />
    <Route path="/password-reset" element={<PasswordResetPage />} />

    <Route path="/onboarding" element={<OnboardingPage />} />
    <Route path="/oauth/:provider/callback" element={<OAuthCallbackPage />} />
  </>
);
