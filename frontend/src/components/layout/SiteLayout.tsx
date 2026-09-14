import { Outlet, useLocation } from 'react-router-dom';
import { CollectProvider } from '../../features/savedTrend/collect/CollectProvider';
import { CollectTray } from '../../features/savedTrend/collect/CollectTray';
import { SiteFooter } from './SiteFooter';
import { SiteHeader } from './SiteHeader';

/*
 * 새 시안으로 다시 그린 화면들이 함께 쓰는 레이아웃입니다. 아직 옛 모양인 화면은
 * AppLayout에 그대로 두고, 여기로 옮겨 온 화면만 .trendin-ui 아래로 들어옵니다.
 */
export function SiteLayout() {
  const location = useLocation();
  // 랜딩은 로그인 전 소개 화면이라 담기 패널까지 띄우지 않습니다.
  const showTray = location.pathname !== '/';

  return (
    <CollectProvider>
      <div className="trendin-ui">
        <SiteHeader />
        <Outlet />
        <SiteFooter />
        {showTray && <CollectTray />}
      </div>
    </CollectProvider>
  );
}
