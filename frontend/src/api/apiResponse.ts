import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';

/** 백엔드 공통 응답 봉투(BaseResponse). 성공 응답의 실제 값은 data에 들어 있습니다. */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string | null;
}

/**
 * 목록 API가 공통으로 쓰는 페이지 응답입니다.
 * 전체 개수나 마지막 페이지 번호는 서버가 주지 않으므로, 더 있는지는 hasNext 로만 판단합니다.
 */
export interface Page<T> {
  content: T[];
  page: number;
  size: number;
  hasNext: boolean;
}


/**
 * 공통 봉투를 벗겨 실제 값만 돌려줍니다.
 * 호출부가 매번 `data.data` 를 적지 않도록, 그리고 봉투 모양이 바뀌면 여기만 고치도록 모아 둡니다.
 */
export async function unwrap<T>(request: Promise<AxiosResponse<ApiResponse<T>>>): Promise<T> {
  const { data } = await request;
  return data.data;
}

/** 실패 응답(ErrorResponse)에는 data가 없고 message만 옵니다. */
interface ApiErrorBody {
  message?: unknown;
}

/**
 * 서버가 내려준 한국어 사유를 그대로 화면에 씁니다.
 * 오류 코드는 응답 본문에 없어서, 코드가 필요한 분기는 상태 코드로 가릅니다.
 */
export function getApiErrorMessage(error: unknown): string | undefined {
  if (!(error instanceof AxiosError)) return undefined;
  const message = (error.response?.data as ApiErrorBody | undefined)?.message;
  return typeof message === 'string' && message.trim() ? message : undefined;
}

export function getApiErrorStatus(error: unknown): number | undefined {
  return error instanceof AxiosError ? error.response?.status : undefined;
}
