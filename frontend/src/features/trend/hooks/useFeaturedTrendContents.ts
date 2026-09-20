import { useQuery } from '@tanstack/react-query';
import { getFeaturedTrendContents } from '../featuredTrendContents';

export function useFeaturedTrendContents() {
  return useQuery({
    queryKey: ['trends', 'featured-contents', 'FASHION', 'CURRENT', '24H'],
    queryFn: getFeaturedTrendContents,
  });
}
