import { Outlet, useLocation } from 'react-router-dom';
import { CollectProvider } from '../../features/savedTrend/collect/CollectProvider';
import { CollectTray } from '../../features/savedTrend/collect/CollectTray';
import { Header } from './Header';

export function AppLayout() {
  const location = useLocation();
  // 저장 페이지 자체가 보드 화면이라 담기 패널을 겹쳐 띄우지 않습니다.
  const showTray = location.pathname !== '/saved';

  return (
    <CollectProvider>
      <Header />
      <Outlet />
      {showTray && <CollectTray />}
    </CollectProvider>
  );
}
