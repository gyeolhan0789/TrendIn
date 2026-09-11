/*
 * 백엔드 LoginRequest의 제약을 그대로 옮겼습니다. 서버가 최종 판정을 하지만,
 * 확실히 틀린 입력까지 왕복시키지 않으려고 같은 기준으로 먼저 거릅니다.
 */
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const maxEmailLength = 254;
const maxPasswordLength = 128;

/** 서버도 이메일을 소문자로 눕혀 저장하므로, 로그인이 가입과 같은 값을 보도록 맞춥니다. */
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

/** 로그인은 길이만 거릅니다. 맞는 비밀번호인지는 서버만 압니다. */
export function validateLoginPassword(password: string): string | undefined {
  if (!password) return '비밀번호를 입력해 주세요.';
  if (password.length > maxPasswordLength) return `비밀번호는 ${maxPasswordLength}자 이하여야 합니다.`;
  return undefined;
}
