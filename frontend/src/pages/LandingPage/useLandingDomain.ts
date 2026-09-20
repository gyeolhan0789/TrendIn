import { useState } from 'react';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import type { DomainOption } from '../../features/onboarding/types/onboarding';

/** 고를 것이 여럿이면 패션부터 보여 줍니다. 랜딩이 앞세우는 분야입니다. */
const PREFERRED_DOMAIN = 'FASHION';

export interface LandingDomain {
  /** 고를 수 있는 분야. 로그인 여부에 따라 내 분야이거나 전체입니다. */
  domains: DomainOption[];
  /** 지금 보고 있는 분야. 목록을 아직 못 받았으면 비어 있습니다. */
  domain: string | undefined;
  /** 고르개에 그대로 넘기는 목록. 고를 것이 없으면 사정을 적은 한 줄이 들어 있습니다. */
  options: { value: string; label: string }[];
  pick: (value: string) => void;
  /** 로그인은 했는데 고른 분야가 하나도 없는 경우. 받는 중인 것과 다릅니다. */
  noChosenDomain: boolean;
  loggedIn: boolean;
}

/**
 * 랜딩의 두 구역(오늘의 트렌드 · 지금 주목할 만한 콘텐츠)이 같은 분야를 봐야 해서
 * 고르는 일을 여기 한 곳에 둡니다. 한쪽에서 바꾸면 다른 쪽도 함께 따라갑니다.
 */
export function useLandingDomain(): LandingDomain {
  const session = useAuthSession();

  /*
   * 로그인했으면 내가 고른 분야만, 아니면 고를 수 있는 분야 전체를 내놓습니다.
   * 로그인 전에는 고른 분야라는 것이 없어 전체를 보여 주는 편이 맞습니다.
   *
   * 내 분야 조회는 토큰을 요구하므로 로그인 전에는 아예 묻지 않습니다. 물으면 401 이 나고
   * 인터셉터가 토큰을 다시 받으러 갑니다.
   */
  const allDomainsQuery = useDomains();
  const myDomainsQuery = useMyDomains(Boolean(session));
  const domainsQuery = session ? myDomainsQuery : allDomainsQuery;
  const domains = domainsQuery.data ?? [];
  const noChosenDomain = domainsQuery.isSuccess && domains.length === 0;

  const [picked, setPicked] = useState<string>();
  /*
   * 고른 값이 목록에 없으면 기본값으로 되돌립니다. 로그인하면서 목록이 전체에서 내 분야로
   * 좁아지는 순간이 있어, 고른 값이 남의 분야로 남지 않게 합니다.
   */
  const domain = domains.some((option) => option.domain === picked)
    ? picked
    : domains.find((option) => option.domain === PREFERRED_DOMAIN)?.domain ?? domains[0]?.domain;

  const options = domains.length > 0
    ? domains.map((option) => ({ value: option.domain, label: option.name }))
    : [{ value: '', label: emptyLabel(domainsQuery.isError, noChosenDomain) }];

  return { domains, domain, options, pick: setPicked, noChosenDomain, loggedIn: Boolean(session) };
}

/** 고를 것이 없을 때 칸을 비워 두면 무엇을 기다리는지 알 수 없어, 사정을 적어 둡니다. */
function emptyLabel(isError: boolean, noChosen: boolean) {
  if (isError) return '불러오지 못함';
  return noChosen ? '고른 분야 없음' : '불러오는 중…';
}
