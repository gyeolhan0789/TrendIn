import { Route } from 'react-router-dom';
import { HomePage } from '../../pages/HomePage/HomePage';
import { TrendDetailPage } from '../../pages/TrendDetailPage/TrendDetailPage';

export const appRoutes = (
  <>
    <Route path="/" element={<HomePage />} />
    <Route path="/trends/:trendId" element={<TrendDetailPage />} />
  </>
);

