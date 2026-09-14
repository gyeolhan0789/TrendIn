import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { appRoutes, authRoutes, landingRoutes } from './routes';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {landingRoutes}
        {authRoutes}
        <Route element={<AppLayout />}>{appRoutes}</Route>
      </Routes>
    </BrowserRouter>
  );
}
