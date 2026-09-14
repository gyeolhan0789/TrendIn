import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { SiteLayout } from '../../components/layout/SiteLayout';
import { appRoutes, authRoutes, siteRoutes } from './routes';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {authRoutes}
        <Route element={<SiteLayout />}>{siteRoutes}</Route>
        <Route element={<AppLayout />}>{appRoutes}</Route>
      </Routes>
    </BrowserRouter>
  );
}
