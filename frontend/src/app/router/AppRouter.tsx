import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { RequireAuth } from './RequireAuth';
import { appRoutes, authRoutes } from './routes';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {authRoutes}
        {/* 대시보드 화면은 모두 토큰이 있어야 자료를 받을 수 있어 로그인 여부를 먼저 확인합니다. */}
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>{appRoutes}</Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
