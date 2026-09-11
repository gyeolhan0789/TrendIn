import { Route } from 'react-router-dom';
import { HomePage } from '../../pages/HomePage/HomePage';
import { LoginPage } from '../../pages/LoginPage/LoginPage';
import { MyPage } from '../../pages/MyPage/MyPage';
import { OAuthCallbackPage } from '../../pages/OAuthCallbackPage/OAuthCallbackPage';
import { OnboardingPage } from '../../pages/OnboardingPage/OnboardingPage';
import { SavedTrendPage } from '../../pages/SavedTrendPage/SavedTrendPage';
import { SignUpPage } from '../../pages/SignUpPage/SignUpPage';
import { TrendDetailPage } from '../../pages/TrendDetailPage/TrendDetailPage';

export const appRoutes = (
  <>
    <Route path="/" element={<HomePage />} />
    <Route path="/saved" element={<SavedTrendPage />} />
    <Route path="/trends/:trendId" element={<TrendDetailPage />} />
    <Route path="/mypage" element={<MyPage />} />
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
    <Route path="/onboarding" element={<OnboardingPage />} />
    <Route path="/oauth/:provider/callback" element={<OAuthCallbackPage />} />
  </>
);
