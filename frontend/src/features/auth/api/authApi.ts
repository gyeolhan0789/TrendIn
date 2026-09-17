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
 * 실제 중복 판정은 회원가입 응답의 409가 합니다.
 *
 * 실패는 삼키지 않고 그대로 올립니다. 500을 받고도 아무 일 없던 듯 넘기면, 화면은 확인이
 * 끝난 것처럼 굴면서 사실은 아무것도 확인하지 못한 상태가 됩니다. 확인이 안 됐다는 사실은
 * 확인이 됐다는 사실만큼 화면이 알아야 합니다.
 */
export async function checkEmailAvailable(email: string): Promise<boolean> {
  const { available } = await unwrap(
    apiClient.post<ApiResponse<{ available: boolean }>>(API_ENDPOINTS.auth.emailCheck, { email }),
  );
  return available;
}

export async function oauthLogin(provider: string, request: OAuthLoginRequest): Promise<OAuthLoginResult> {
  return unwrap(
    apiClient.post<ApiResponse<OAuthLoginResult>>(API_ENDPOINTS.auth.oauthLogin(provider), request),
  );
}
