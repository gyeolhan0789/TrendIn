/** 로그인·재발급이 함께 내려주는 토큰 묶음입니다. 만료 시간의 단위는 초입니다. */
export interface AuthTokenBundle {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  accessTokenExpiresIn: number;
  refreshTokenExpiresIn: number;
}

export interface LoginResult extends AuthTokenBundle {
  /** 관심 분야를 한 개 이상 고르기 전까지는 false입니다. */
  onboardingCompleted: boolean;
}

export interface OAuthLoginResult extends LoginResult {
  /** 이번 로그인으로 계정이 새로 만들어졌는지. 환영 문구를 가르는 데만 씁니다. */
  isNewMember: boolean;
}

export interface SignUpRequest {
  email: string;
  password: string;
  nickname: string;
}

export interface SignUpResult {
  memberId: number;
  email: string;
  nickname: string;
  onboardingCompleted: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface OAuthLoginRequest {
  code: string;
  state: string;
}

/**
 * 기기에 보관하는 로그인 세션. 저장 보드·관심 키워드와 같은 방식으로 localStorage에 둡니다.
 * 로그인 응답에는 회원 정보가 없어서, 화면에 보여줄 이메일은 입력값에서 가져옵니다.
 */
export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  email: string;
  onboardingCompleted: boolean;
}
