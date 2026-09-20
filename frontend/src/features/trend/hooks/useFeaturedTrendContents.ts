import { useQuery } from '@tanstack/react-query';
import { getFeaturedTrendContents } from '../featuredTrendContents';

/** 분야를 아직 모르면 부르지 않습니다. 분야가 바뀌면 키가 달라져 다시 받습니다. */
export function useFeaturedTrendContents(domain: string | undefined) {
  return useQuery({
    queryKey: ['trends', 'featured-contents', domain ?? '', 'CURRENT', '24H'],
    queryFn: () => getFeaturedTrendContents(domain as string),
    enabled: Boolean(domain),
  });
}
