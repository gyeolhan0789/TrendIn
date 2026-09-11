import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { showToast } from '../../components/common/toast';
import { AuthField } from '../../features/auth/components/AuthField';
import { AuthShell } from '../../features/auth/components/AuthShell';
import { PasswordChecklist } from '../../features/auth/components/PasswordChecklist';
import { SocialLoginNotice } from '../../features/auth/components/SocialLoginNotice';
import { getAuthSession } from '../../features/auth/api/authSessionStorage';
import { describeAuthError } from '../../features/auth/authErrors';
import { useEmailAvailability } from '../../features/auth/hooks/useEmailAvailability';
import { useSignUp } from '../../features/auth/hooks/useSignUp';
import {
  normalizeEmail,
  validateEmail,
  validateNickname,
  validatePassword,
  validatePasswordConfirm,
} from '../../features/auth/validation';

interface SignUpErrors {
  email?: string;
  nickname?: string;
  password?: string;
  passwordConfirm?: string;
}

export function SignUpPage() {
  const navigate = useNavigate();
  const signUpMutation = useSignUp();
  const [email, setEmail] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [errors, setErrors] = useState<SignUpErrors>({});
  const [formError, setFormError] = useState<string>();
  /** 이메일 칸을 떠날 때 확인을 맡긴 주소입니다. 비어 있으면 아직 확인하지 않은 것입니다. */
  const [checkedEmail, setCheckedEmail] = useState('');

  // 가입 직후 자동 로그인으로 세션이 생기므로, 로그인 화면과 같은 이유로 진입 시점만 봅니다.
  const [enteredLoggedIn] = useState(() => Boolean(getAuthSession()));

  const normalizedEmail = normalizeEmail(email);
  // 가입이 시작되면 캐시를 비우는데, 그때 이 질의가 되살아나 쓸데없이 한 번 더 확인하러 갑니다.
  const availabilityQuery = useEmailAvailability(checkedEmail, Boolean(checkedEmail) && signUpMutation.isIdle);
  // 이메일을 다시 고치면 앞서 받은 확인 결과는 지금 값의 것이 아닙니다.
  const checkedCurrent = checkedEmail === normalizedEmail;
  const available = checkedCurrent ? availabilityQuery.data : undefined;
  const checkingEmail = checkedCurrent && availabilityQuery.isFetching;

  const takenError = available === false ? '이미 가입된 이메일입니다.' : undefined;
  const emailError = errors.email ?? takenError;

  const emailHint = (() => {
    if (checkingEmail) return '이메일을 확인하는 중…';
    // 확인 자체가 실패하면(null) 굳이 알리지 않습니다. 중복은 가입 응답이 최종적으로 가려냅니다.
    if (available === true) return '사용할 수 있는 이메일입니다.';
    return undefined;
  })();

  const checkEmail = () => {
    const message = validateEmail(email);
    setErrors((current) => ({ ...current, email: message }));
    setCheckedEmail(message ? '' : normalizedEmail);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: SignUpErrors = {
      email: validateEmail(email),
      nickname: validateNickname(nickname),
      password: validatePassword(password),
      passwordConfirm: validatePasswordConfirm(password, passwordConfirm),
    };
    setErrors(nextErrors);
    setFormError(undefined);
    if (Object.values(nextErrors).some(Boolean) || takenError) return;

    try {
      const { member, session } = await signUpMutation.mutateAsync({ email, password, nickname });
      if (!session) {
        showToast({ message: `${member.nickname}님, 가입했습니다. 로그인해 주세요.`, type: 'success' });
        navigate('/login', { replace: true });
        return;
      }
      showToast({ message: `${member.nickname}님, 환영합니다. 먼저 관심 분야를 골라 주세요.`, type: 'success' });
      // 가입 직후에는 온보딩이 끝나지 않았으므로 관심 분야 선택부터 거칩니다.
      navigate(session.onboardingCompleted ? '/' : '/onboarding', { replace: true });
    } catch (error) {
      setFormError(describeAuthError(error, '가입하지 못했습니다. 잠시 후 다시 시도해 주세요.'));
    }
  };

  if (enteredLoggedIn) return <Navigate to="/" replace />;

  return (
    <AuthShell
      eyebrow="SIGN UP"
      title="관심 키워드부터 시작합니다"
      description="계정을 만들면 키워드의 추이를 추적하고 트렌드를 보드에 모을 수 있습니다."
      footer={<>이미 계정이 있으신가요? <Link to="/login">로그인</Link></>}
    >
      <form className="auth-form" onSubmit={submit} noValidate>
        <AuthField
          label="이메일"
          type="email"
          value={email}
          onChange={setEmail}
          onBlur={checkEmail}
          placeholder="you@company.co.kr"
          autoComplete="email"
          error={emailError}
          hint={emailHint}
          disabled={signUpMutation.isPending}
        />
        <AuthField
          label="닉네임"
          value={nickname}
          onChange={setNickname}
          onBlur={() => setErrors((current) => ({ ...current, nickname: validateNickname(nickname) }))}
          placeholder="2~30자"
          autoComplete="nickname"
          error={errors.nickname}
          disabled={signUpMutation.isPending}
        />
        <AuthField
          label="비밀번호"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="영문, 숫자, 특수문자를 모두 포함해 10자 이상"
          autoComplete="new-password"
          error={errors.password}
          hint={<PasswordChecklist password={password} />}
          disabled={signUpMutation.isPending}
        />
        <AuthField
          label="비밀번호 확인"
          type="password"
          value={passwordConfirm}
          onChange={setPasswordConfirm}
          onBlur={() => setErrors((current) => ({ ...current, passwordConfirm: validatePasswordConfirm(password, passwordConfirm) }))}
          placeholder="비밀번호를 한 번 더 입력하세요"
          autoComplete="new-password"
          error={errors.passwordConfirm}
          disabled={signUpMutation.isPending}
        />

        {formError && <p className="auth-alert" role="alert">{formError}</p>}

        <Button className="auth-submit" type="submit" isLoading={signUpMutation.isPending}>
          {signUpMutation.isPending ? '가입하는 중…' : '가입하고 시작하기'}
        </Button>
      </form>

      <SocialLoginNotice />
    </AuthShell>
  );
}
