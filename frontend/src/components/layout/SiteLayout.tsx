import { Outlet } from 'react-router-dom';
import { SiteFooter } from './SiteFooter';
import { SiteHeader } from './SiteHeader';

/*
 * 새 시안으로 다시 그린 화면들이 함께 쓰는 레이아웃입니다. 아직 옛 모양인 화면은
 * AppLayout에 그대로 두고, 여기로 옮겨 온 화면만 .trendin-ui 아래로 들어옵니다.
 */
export function SiteLayout() {
  return (
    <div className="trendin-ui">
      <SiteHeader />
      <Outlet />
      <SiteFooter />
    </div>
  );
}
