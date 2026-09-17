/*
 * 백엔드 SignUpRequest의 제약을 그대로 옮겼습니다. 서버가 최종 판정을 하지만,
 * 확실히 틀린 입력까지 왕복시키지 않으려고 같은 기준으로 먼저 거릅니다.
 */
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const maxEmailLength = 254;
const minNicknameLength = 2;
const maxNicknameLength = 30;
const minPasswordLength = 8;
const maxPasswordLength = 128;

/** 비밀번호 규칙은 입력하는 동안 체크리스트로도 보여주므로 항목별로 나눠 둡니다. */
export const passwordRules: { label: string; test: (password: string) => boolean }[] = [
  { label: `${minPasswordLength}자 이상`, test: (password) => password.length >= minPasswordLength },
  { label: '영문 포함', test: (password) => /[A-Za-z]/.test(password) },
  { label: '숫자 포함', test: (password) => /[0-9]/.test(password) },
  { label: '특수문자 포함', test: (password) => /[^A-Za-z0-9]/.test(password) },
];

/** 서버도 이메일을 소문자로 눕혀 저장하므로, 중복 확인과 로그인이 같은 값을 보도록 맞춥니다. */
export function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

export function validateEmail(email: string): string | undefined {
  const value = normalizeEmail(email);
  if (!value) return '이메일을 입력해 주세요.';
  if (value.length > maxEmailLength) return `이메일은 ${maxEmailLength}자 이하여야 합니다.`;
  if (!emailPattern.test(value)) return '이메일 형식이 올바르지 않습니다.';
  return undefined;
}

export function validateNickname(nickname: string): string | undefined {
  const value = nickname.trim();
  if (!value) return '닉네임을 입력해 주세요.';
  if (value.length < minNicknameLength || value.length > maxNicknameLength) {
    return `닉네임은 ${minNicknameLength}자 이상 ${maxNicknameLength}자 이하여야 합니다.`;
  }
  return undefined;
}

export function validatePassword(password: string): string | undefined {
  if (!password) return '비밀번호를 입력해 주세요.';
  if (password.length > maxPasswordLength) return `비밀번호는 ${maxPasswordLength}자 이하여야 합니다.`;
  if (passwordRules.every((rule) => rule.test(password))) return undefined;
  // 이름표 옆 한 줄에 들어가야 해서 짧게 씁니다. 어느 조건이 모자란지는 아래 체크리스트가 짚어 줍니다.
  return `영문·숫자·특수문자를 포함해 ${minPasswordLength}자 이상이어야 합니다.`;
}

/** 로그인은 길이·형식만 거릅니다. 맞는 비밀번호인지는 서버만 압니다. */
export function validateLoginPassword(password: string): string | undefined {
  if (!password) return '비밀번호를 입력해 주세요.';
  if (password.length > maxPasswordLength) return `비밀번호는 ${maxPasswordLength}자 이하여야 합니다.`;
  return undefined;
}

/**
 * 메일로 받은 인증번호. 맞는 번호인지는 서버만 알고, 여기서는 빈 칸만 거릅니다.
 * 자릿수를 짐작해 막으면, 서버가 형식을 바꾸는 날 맞는 번호까지 함께 막힙니다.
 */
export function validateVerificationCode(code: string): string | undefined {
  if (!code.trim()) return '인증번호를 입력해 주세요.';
  return undefined;
}

export function validatePasswordConfirm(password: string, confirm: string): string | undefined {

  if (!confirm) return '비밀번호를 한 번 더 입력해 주세요.';
  if (password !== confirm) return '비밀번호가 일치하지 않습니다.';
  return undefined;
}
