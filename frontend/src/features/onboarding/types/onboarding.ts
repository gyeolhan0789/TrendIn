/**
 * 서비스가 제공하는 관심 분야. 백엔드가 enum으로 관리해서 목록이 바뀌려면 배포가 필요하고,
 * 그래서 화면도 코드를 박아 두지 않고 GET /domains 가 준 것만 그립니다.
 */
export interface DomainOption {
  /** 서버로 돌려보낼 코드. 예: DEVELOP */
  domain: string;
  /** 사람이 읽는 이름. 예: 개발 */
  name: string;
}
