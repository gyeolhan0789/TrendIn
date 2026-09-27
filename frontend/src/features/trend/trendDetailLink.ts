import { useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import type { Location } from 'react-router-dom';
import { trendDetailSearch } from '../../constants/filterCodes';

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
 * 코드로 옮길 때는 `const { to, state, replace } = openDetail(id)` 로 나눠 씁니다.
 *
 * **상세 위에서 다른 상세를 열면 뒤 화면을 물려받고 이력을 바꿔치기합니다.** 상세가 닫히는 도중에
 * 뒤 화면의 다른 트렌드를 누르면 지금 주소가 아직 상세라, 그대로 두면 뒤 화면이 '앞 상세'가 되고
 * 이력에 상세가 두 칸 쌓입니다. 그러면 닫기(뒤로 가기)가 앞 상세로 돌아가 닫히는 중인 패널이
 * 그대로 멈춰 서고, 새로고침해야 풀렸습니다.
 */
export function useTrendDetailLink() {
  const location = useLocation();

  return useCallback(
    (trendId: number, search = '') => {
      const background = (location.state as TrendDetailLocationState | null)?.backgroundLocation;
      return {
        to: { pathname: `/trends/${trendId}`, search: trendDetailSearch(location.search, search) },
        state: { backgroundLocation: background ?? location } satisfies TrendDetailLocationState,
        replace: Boolean(background),
      };
    },
    [location],
  );
}
