import { apiClient } from '../../../api/client';
import type { ApiResponse } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type {
  LoginRequest,
  LoginResult,
  OAuthLoginRequest,
  OAuthLoginResult,
} from '../types/auth';

export async function login(request: LoginRequest): Promise<LoginResult> {
  const { data } = await apiClient.post<ApiResponse<LoginResult>>(API_ENDPOINTS.auth.login, request);
  return data.data;
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post<ApiResponse<null>>(API_ENDPOINTS.auth.logout, { refreshToken });
}

export async function oauthLogin(provider: string, request: OAuthLoginRequest): Promise<OAuthLoginResult> {
  const { data } = await apiClient.post<ApiResponse<OAuthLoginResult>>(
    API_ENDPOINTS.auth.oauthLogin(provider),
    request,
  );
  return data.data;
}
