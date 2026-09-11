import { getApiErrorMessage, getApiErrorStatus } from '../../api/apiResponse';

/**
 * 서버가 내려준 한국어 사유가 있으면 그대로 보여줍니다.
 * 응답 자체가 없으면 회선 문제라, 자격증명을 의심하게 만드는 문구 대신 재시도를 권합니다.
 */
export function describeAuthError(error: unknown, fallback: string): string {
  const message = getApiErrorMessage(error);
  if (message) return message;
  if (getApiErrorStatus(error) === undefined) return '네트워크 상태를 확인한 뒤 다시 시도해 주세요.';
  return fallback;
}
