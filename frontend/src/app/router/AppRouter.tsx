import { Suspense } from 'react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { SiteLayout } from '../../components/layout/SiteLayout';
import { RequireAuth } from './RequireAuth';
import { appRoutes, authRoutes, landingRoutes, siteRoutes, stageRoutes } from './routes';
import type { TrendDetailLocationState } from '../../features/trend/trendDetailLink';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="trendin-state" role="status">화면을 불러오는 중입니다.</div>}>
        <RoutedScreens />
      </Suspense>
    </BrowserRouter>
  );
}

/*
 * 트렌드 상세는 화면을 갈아 끼우는 대신 보던 화면 위에 패널로 뜹니다. 그래서 주소가
 * /trends/:id 여도 길찾기는 뒤에 둘 화면(backgroundLocation)으로 하고, 상세는 그 위에 따로
 * 얹습니다. 뒤 화면이 제 레이아웃 그대로 남아 있어야 닫았을 때 있던 자리로 돌아갑니다.
 *
 * 주소를 바로 열었거나 새로고침으로 들어오면 뒤에 둘 화면이 없습니다. 그때는 상세가 평소처럼
 * 제 경로로 잡혀 AppLayout 안에서 기본 화면을 뒤에 세웁니다.
 */
function RoutedScreens() {
  const location = useLocation();
  const backgroundLocation = (location.state as TrendDetailLocationState | null)?.backgroundLocation;

  return (
    <>
      <Routes location={backgroundLocation ?? location}>
        {authRoutes}
        {/* 새 시안 화면들. 랜딩만 가드 밖이고 나머지는 토큰이 있어야 자료를 받습니다. */}
        <Route element={<SiteLayout />}>
          {landingRoutes}
          <Route element={<RequireAuth />}>{siteRoutes}</Route>
        </Route>
        {/* 지도가 창을 가득 채우는 화면. 머리말만 얹고 푸터는 두지 않습니다. */}
        <Route element={<SiteLayout stage />}>
          <Route element={<RequireAuth />}>{stageRoutes}</Route>
        </Route>
        {/* 대시보드 화면은 모두 토큰이 있어야 자료를 받을 수 있어 로그인 여부를 먼저 확인합니다. */}
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>{appRoutes}</Route>
        </Route>
      </Routes>
      {backgroundLocation && (
        <Routes>
          <Route element={<RequireAuth />}>{appRoutes}</Route>
        </Routes>
      )}
    </>
  );
}
