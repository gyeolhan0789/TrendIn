import axios, { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { API_ENDPOINTS } from '../constants/apiEndpoints';
import {
  clearAuthSession,
  getAuthSession,
  replaceSessionTokens,
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
  const session = getAuthSession();
  if (!session) return undefined;
  try {
    const { data } = await reissueClient.post<ApiResponse<LoginResult>>(
      API_ENDPOINTS.auth.reissue,
      { refreshToken: session.refreshToken },
    );
    return replaceSessionTokens(data.data, data.data.onboardingCompleted);
  } catch {
    // Refresh Token까지 만료됐으면 되살릴 방법이 없어 세션을 비우고 로그아웃 상태로 둡니다.
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
