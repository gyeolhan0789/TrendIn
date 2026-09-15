import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { SiteLayout } from '../../components/layout/SiteLayout';
import { RequireAuth } from './RequireAuth';
import { appRoutes, authRoutes, landingRoutes, siteRoutes } from './routes';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {authRoutes}
        {/* 새 시안 화면들. 랜딩만 가드 밖이고 나머지는 토큰이 있어야 자료를 받습니다. */}
        <Route element={<SiteLayout />}>
          {landingRoutes}
          <Route element={<RequireAuth />}>{siteRoutes}</Route>
        </Route>
        {/* 대시보드 화면은 모두 토큰이 있어야 자료를 받을 수 있어 로그인 여부를 먼저 확인합니다. */}
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>{appRoutes}</Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
