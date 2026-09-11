import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { showToast } from '../../components/common/toast';
import { AuthField } from '../../features/auth/components/AuthField';
import { AuthShell } from '../../features/auth/components/AuthShell';
import { SocialLoginNotice } from '../../features/auth/components/SocialLoginNotice';
import { getAuthSession } from '../../features/auth/api/authSessionStorage';
import { describeAuthError } from '../../features/auth/authErrors';
import { useLogin } from '../../features/auth/hooks/useLogin';
import { validateEmail, validateLoginPassword } from '../../features/auth/validation';

interface LoginLocationState {
  /** 로그인 화면으로 보내기 전에 가려던 경로. 없으면 대시보드로 돌려보냅니다. */
  from?: string;
}

interface LoginErrors {
  email?: string;
  password?: string;
}

export function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const loginMutation = useLogin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<LoginErrors>({});
  const [formError, setFormError] = useState<string>();

  const from = (location.state as LoginLocationState | null)?.from ?? '/';
  /*
   * 로그인에 성공하면 세션이 생기면서 이 화면이 다시 그려집니다. 그때도 아래 리다이렉트가 돌면
   * 온보딩 분기를 앞질러 버려서, 들어올 때 이미 로그인 상태였는지만 한 번 붙잡아 둡니다.
   */
  const [enteredLoggedIn] = useState(() => Boolean(getAuthSession()));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: LoginErrors = {
      email: validateEmail(email),
      password: validateLoginPassword(password),
    };
    setErrors(nextErrors);
    setFormError(undefined);
    if (nextErrors.email || nextErrors.password) return;

    try {
      const result = await loginMutation.mutateAsync({ email, password });
      // 관심 분야를 아직 고르지 않은 계정은 온보딩부터 마치게 합니다.
      showToast({
        message: result.onboardingCompleted ? '로그인했습니다.' : '먼저 관심 분야를 골라 주세요.',
        type: 'success',
      });
      navigate(result.onboardingCompleted ? from : '/onboarding', { replace: true });
    } catch (error) {
      setFormError(describeAuthError(error, '로그인하지 못했습니다. 잠시 후 다시 시도해 주세요.'));
    }
  };

  if (enteredLoggedIn) return <Navigate to={from} replace />;

  return (
    <AuthShell
      eyebrow="SIGN IN"
      title="다시 만나 반갑습니다"
      description="등록한 관심 키워드의 추이와 저장한 트렌드를 이어서 봅니다."
      footer={<>아직 계정이 없으신가요? <Link to="/signup">회원가입</Link></>}
    >
      <form className="auth-form" onSubmit={submit} noValidate>
        <AuthField
          label="이메일"
          type="email"
          value={email}
          onChange={setEmail}
          onBlur={() => setErrors((current) => ({ ...current, email: validateEmail(email) }))}
          placeholder="you@company.co.kr"
          autoComplete="email"
          error={errors.email}
          disabled={loginMutation.isPending}
        />
        <AuthField
          label="비밀번호"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="비밀번호를 입력하세요"
          autoComplete="current-password"
          error={errors.password}
          disabled={loginMutation.isPending}
        />

        {formError && <p className="auth-alert" role="alert">{formError}</p>}

        <Button className="auth-submit" type="submit" isLoading={loginMutation.isPending}>
          {loginMutation.isPending ? '로그인 중…' : '로그인'}
        </Button>
      </form>

      <SocialLoginNotice />
    </AuthShell>
  );
}
