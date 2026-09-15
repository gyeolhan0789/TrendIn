import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';

/**
 * 로그인한 사람에게만 열리는 화면을 감쌉니다.
 *
 * 백엔드는 분야 목록과 인증 API를 빼면 모든 조회에 토큰을 요구합니다. 그래서 로그인 없이 대시보드를
 * 열어 두면 화면은 그려지지만 모든 요청이 401로 떨어집니다. 빈 화면을 보여 주는 대신 로그인으로 보냅니다.
 *
 * 로그인 뒤 원래 보려던 자리로 돌아올 수 있도록 경로를 함께 넘깁니다.
 */
export function RequireAuth() {
  const session = useAuthSession();
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  }

  return <Outlet />;
}
