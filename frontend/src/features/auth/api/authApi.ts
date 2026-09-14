import { apiClient } from '../../../api/client';
import type { ApiResponse } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type {
  LoginRequest,
  LoginResult,
  OAuthLoginRequest,
  OAuthLoginResult,
  SignUpRequest,
  SignUpResult,
} from '../types/auth';

export async function signUp(request: SignUpRequest): Promise<SignUpResult> {
  return unwrap(apiClient.post<ApiResponse<SignUpResult>>(API_ENDPOINTS.auth.signUp, request));
}

export async function login(request: LoginRequest): Promise<LoginResult> {
  return unwrap(apiClient.post<ApiResponse<LoginResult>>(API_ENDPOINTS.auth.login, request));
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post<ApiResponse<null>>(API_ENDPOINTS.auth.logout, { refreshToken });
}

/**
 * 가입 전 이메일을 미리 확인합니다. 확인한 뒤에도 상태가 바뀔 수 있어 결과는 안내용이고,
 * 실제 중복 판정은 회원가입 응답의 409가 합니다. 그래서 확인하지 못하면 막지 않고 null을 돌려줍니다.
 */
export async function checkEmailAvailable(email: string): Promise<boolean | null> {
  try {
    const { available } = await unwrap(
      apiClient.post<ApiResponse<{ available: boolean }>>(API_ENDPOINTS.auth.emailCheck, { email }),
    );
    return available;
  } catch {
    return null;
  }
}

export async function oauthLogin(provider: string, request: OAuthLoginRequest): Promise<OAuthLoginResult> {
  return unwrap(
    apiClient.post<ApiResponse<OAuthLoginResult>>(API_ENDPOINTS.auth.oauthLogin(provider), request),
  );
}
