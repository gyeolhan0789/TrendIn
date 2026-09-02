import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { appRoutes } from './routes';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>{appRoutes}</Route>
      </Routes>
    </BrowserRouter>
  );
}

