import axios, { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { API_ENDPOINTS } from '../constants/apiEndpoints';
import {
  clearAuthSession,
  getAuthSession,
  replaceSessionTokens,
  syncAuthSessionFromStorage,
} from '../features/auth/api/authSessionStorage';
import type { ApiResponse } from './apiResponse';
import type { AuthSession, LoginResult } from '../features/auth/types/auth';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '';
const timeout = 10_000;
const jsonHeaders = { 'Content-Type': 'application/json' };

export const apiClient = axios.create({ baseURL, timeout, headers: jsonHeaders });

/*
 * 재발급은 만료된 Access Token을 달지 않아야 하고, 그 응답의 401을 다시 가로채면
 * 무한히 되돌아오므로 인터셉터가 붙지 않은 별도 인스턴스로 보냅니다.
 */
const reissueClient = axios.create({ baseURL, timeout, headers: jsonHeaders });

interface RetriableRequest extends InternalAxiosRequestConfig {
  retriedAfterReissue?: boolean;
}

/** 자격증명 자체를 다루는 요청은 401이 정상 응답이라 재발급으로 넘기지 않습니다. */
const credentialPaths: string[] = [API_ENDPOINTS.auth.login, API_ENDPOINTS.auth.reissue];

apiClient.interceptors.request.use((config) => {
  const session = getAuthSession();
  if (session && !config.headers.Authorization) {
    config.headers.Authorization = `${session.tokenType} ${session.accessToken}`;
  }
  return config;
});

async function requestReissue(): Promise<AuthSession | undefined> {
  // 옆 탭이 이미 토큰을 갈아 끼웠을 수 있어, 메모리에 둔 값 대신 저장소의 최신 값으로 보냅니다.
  const session = syncAuthSessionFromStorage();
  if (!session) return undefined;
  try {
    const { data } = await reissueClient.post<ApiResponse<LoginResult>>(
      API_ENDPOINTS.auth.reissue,
      { refreshToken: session.refreshToken },
    );
    return replaceSessionTokens(data.data, data.data.onboardingCompleted);
  } catch {
    /*
     * 서버는 쓰인 Refresh Token을 즉시 회전시킵니다. 옆 탭이 같은 순간에 재발급을 마쳤다면
     * 우리가 보낸 토큰은 이미 무효라 실패합니다. 이때 저장소에 새 토큰이 들어와 있으면
     * 세션 자체는 멀쩡하므로, 로그아웃시키지 않고 그 토큰을 이어받습니다.
     */
    const latest = syncAuthSessionFromStorage();
    if (latest && latest.refreshToken !== session.refreshToken) return latest;

    // 여기까지 왔으면 Refresh Token도 만료됐거나 로그아웃된 것이라 되살릴 방법이 없습니다.
    clearAuthSession();
    return undefined;
  }
}

// 동시에 401을 받은 요청들이 각자 재발급을 부르지 않도록 진행 중인 하나를 함께 기다립니다.
let reissuing: Promise<AuthSession | undefined> | undefined;

function reissueOnce() {
  reissuing ??= requestReissue().finally(() => { reissuing = undefined; });
  return reissuing;
}

apiClient.interceptors.response.use(undefined, async (error: AxiosError) => {
  const request = error.config as RetriableRequest | undefined;
  const retriable = error.response?.status === 401
    && Boolean(request)
    && !request?.retriedAfterReissue
    && !credentialPaths.includes(request?.url ?? '')
    && Boolean(getAuthSession());
  if (!retriable || !request) return Promise.reject(error);

  const renewed = await reissueOnce();
  if (!renewed) return Promise.reject(error);

  request.retriedAfterReissue = true;
  request.headers.Authorization = `${renewed.tokenType} ${renewed.accessToken}`;
  return apiClient(request);
});
