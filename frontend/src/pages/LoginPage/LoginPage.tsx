import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Spinner } from '../../components/common/Spinner';
import { showToast } from '../../components/common/toast';
import { AuthScene } from '../../features/auth/components/AuthScene';
import { AuthSceneField } from '../../features/auth/components/AuthSceneField';
import { LockIcon, MailIcon } from '../../features/auth/components/authIcons';
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
    <AuthScene>
      <div className="auth-scene-card">
        <h2>로그인</h2>
        <p className="auth-scene-card-lead">TrendIn과 함께 더 빠르게,<br />세상의 트렌드를 발견하세요.</p>

        <form className="auth-scene-form" onSubmit={submit} noValidate>
          <AuthSceneField
            label="이메일"
            icon={<MailIcon />}
            type="email"
            value={email}
            onChange={(value) => {
              setEmail(value);
              // 고치는 중에 앞선 오류가 남아 있으면, 이미 고친 값을 틀렸다고 하는 셈입니다.
              setErrors((current) => (current.email ? { ...current, email: undefined } : current));
            }}
            onBlur={() => setErrors((current) => ({ ...current, email: validateEmail(email) }))}
            placeholder="이메일을 입력해주세요."
            autoComplete="email"
            error={errors.email}
            disabled={loginMutation.isPending}
          />
          <AuthSceneField
            label="비밀번호"
            icon={<LockIcon />}
            type="password"
            value={password}
            onChange={(value) => {
              setPassword(value);
              setErrors((current) => (current.password ? { ...current, password: undefined } : current));
            }}
            placeholder="비밀번호를 입력해주세요."
            autoComplete="current-password"
            error={errors.password}
            disabled={loginMutation.isPending}
          />

          {formError && <p className="auth-scene-alert" role="alert">{formError}</p>}

          {/* 시안은 여기서 '로그인 상태 유지'와 한 줄을 나눠 씁니다. 상태 유지는 아직 붙일 동작이 없어 찾기만 답니다. */}
          <p className="login-forgot"><Link to="/password-reset">비밀번호 찾기</Link></p>

          <button className="auth-scene-submit" type="submit" disabled={loginMutation.isPending}>

            {loginMutation.isPending && <Spinner size="small" />}
            {loginMutation.isPending ? '로그인 중…' : '로그인'}
          </button>
        </form>

        <p className="auth-scene-card-foot">처음이신가요? <Link to="/signup">회원가입</Link></p>
      </div>
    </AuthScene>
  );
}
