import { useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import type { Location } from 'react-router-dom';

/**
 * 상세를 열기 직전에 보던 화면입니다.
 *
 * 상세는 목록 위에 뜨는 패널이라 뒤에 그 화면이 그대로 남아야 하고, 닫으면 같은 자리로 돌아가야
 * 합니다. 어느 화면에서 눌렀는지는 누른 쪽만 알고 있어서 주소와 함께 넘깁니다. 주소를 바로 열어
 * 이 값이 없으면 상세가 알아서 기본 화면을 뒤에 세웁니다.
 */
export interface TrendDetailLocationState {
  backgroundLocation: Location;
}

/**
 * 트렌드 상세로 가는 링크를 만듭니다. `<Link {...openDetail(trendId)}>` 처럼 펼쳐 쓰고,
 * 코드로 옮길 때는 `const { to, state } = openDetail(id)` 로 나눠 씁니다.
 */
export function useTrendDetailLink() {
  const location = useLocation();

  return useCallback(
    (trendId: number, search = '') => ({
      to: { pathname: `/trends/${trendId}`, search },
      state: { backgroundLocation: location } satisfies TrendDetailLocationState,
    }),
    [location],
  );
}
