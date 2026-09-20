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

// Vite 밖(테스트)에서도 이 모듈을 불러올 수 있도록 값이 통째로 없는 경우까지 받아 둡니다.
const baseURL = import.meta.env?.VITE_API_BASE_URL ?? '';
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

/**
 * 재발급이 실패했을 때, 이 기기의 세션을 버려야 하는 실패인지 가립니다.
 *
 * 서버가 토큰을 보고 거절한 것(401)과 아예 받지도 못한 것(타임아웃·끊긴 연결·5xx)은 다릅니다.
 * 뒤엣것까지 로그아웃으로 치면 잠깐 끊긴 사이에 멀쩡한 세션을 버리게 됩니다.
 * Refresh Token은 14일짜리라 정말 만료되는 일보다 이쪽이 훨씬 잦습니다.
 */
function sessionRejected(error: unknown) {
  const status = error instanceof AxiosError ? error.response?.status : undefined;
  return status === 400 || status === 401;
}

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
  } catch (error) {
    /*
     * 서버는 쓰인 Refresh Token을 즉시 회전시킵니다. 옆 탭이 같은 순간에 재발급을 마쳤다면
     * 우리가 보낸 토큰은 이미 무효라 실패합니다. 이때 저장소에 새 토큰이 들어와 있으면
     * 세션 자체는 멀쩡하므로, 로그아웃시키지 않고 그 토큰을 이어받습니다.
     */
    const latest = syncAuthSessionFromStorage();
    if (latest && latest.refreshToken !== session.refreshToken) return latest;

    // 서버가 토큰을 거절했을 때만 되살릴 방법이 없습니다. 나머지는 이번 요청만 실패로 둡니다.
    if (sessionRejected(error)) clearAuthSession();
    return undefined;
  }
}

/*
 * 동시에 401을 받은 요청들이 각자 재발급을 부르지 않도록 진행 중인 하나를 함께 기다립니다.
 *
 * 끝난 뒤에도 잠시 그 결과를 그대로 내어 줍니다. 먼저 나가 있던 요청의 401은 재발급이 끝난
 * 다음에야 도착하는데, 그때 또 재발급을 걸면 방금 회전시켜 무효가 된 토큰을 다시 보내게 되고
 * 서버는 이미 쓴 토큰이라며 거절합니다. 그 거절 하나에 멀쩡한 세션이 통째로 날아갑니다.
 */
const REISSUE_REUSE_MS = 3_000;

let reissuing: Promise<AuthSession | undefined> | undefined;

function reissueOnce() {
  if (reissuing) return reissuing;
  const pending = requestReissue();
  reissuing = pending;
  void pending.then(() => {
    setTimeout(() => { if (reissuing === pending) reissuing = undefined; }, REISSUE_REUSE_MS);
  });
  return pending;
}

apiClient.interceptors.response.use(undefined, async (error: AxiosError) => {
  const request = error.config as RetriableRequest | undefined;
  const unauthorized = error.response?.status === 401
    && Boolean(request)
    && !credentialPaths.includes(request?.url ?? '')
    && Boolean(getAuthSession());
  if (!unauthorized || !request) return Promise.reject(error);

  /*
   * 새로 받은 토큰으로 다시 물었는데도 401이면 이 기기의 세션으로 할 수 있는 일이 없습니다.
   * 실패로만 두면 화면은 자료를 못 받은 채 그 자리에 머무르므로, 세션을 비워
   * 로그인으로 보냅니다(RequireAuth).
   */
  if (request.retriedAfterReissue) {
    // 로그아웃은 화면이 스스로 세션을 정리합니다. 여기서 먼저 지우면 서버에서 지울 토큰까지 잃습니다.
    if (request.url !== API_ENDPOINTS.auth.logout) clearAuthSession();
    return Promise.reject(error);
  }

  const renewed = await reissueOnce();
  if (!renewed) return Promise.reject(error);

  request.retriedAfterReissue = true;
  request.headers.Authorization = `${renewed.tokenType} ${renewed.accessToken}`;
  return apiClient(request);
});
