import { Outlet } from 'react-router-dom';
import { SiteFooter } from './SiteFooter';
import { SiteHeader } from './SiteHeader';

interface SiteLayoutProps {
  /*
   * 지도처럼 창 높이에 맞춰 한 화면에서 끝나는 화면을 위한 모양입니다. 스크롤이 없으니
   * 아래로 내려가야 보이는 푸터는 닿을 길이 없어 아예 세우지 않습니다.
   */
  stage?: boolean;
}

/*
 * 새 시안으로 다시 그린 화면들이 함께 쓰는 레이아웃입니다. 아직 옛 모양인 화면은
 * AppLayout에 그대로 두고, 여기로 옮겨 온 화면만 .trendin-ui 아래로 들어옵니다.
 */
export function SiteLayout({ stage = false }: SiteLayoutProps) {
  return (
    <div className={`trendin-ui${stage ? ' trendin-ui--stage' : ''}`}>
      <SiteHeader />
      <Outlet />
      {!stage && <SiteFooter />}
    </div>
  );
}
