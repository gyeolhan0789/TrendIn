import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Spinner } from '../../components/common/Spinner';
import { showToast } from '../../components/common/toast';
import { AuthScene } from '../../features/auth/components/AuthScene';
import { AuthSceneField } from '../../features/auth/components/AuthSceneField';
import { CheckCircleIcon, LockIcon, MailIcon } from '../../features/auth/components/authIcons';
import { PasswordChecklist } from '../../features/auth/components/PasswordChecklist';
import { describeAuthError } from '../../features/auth/authErrors';
import {
  useRequestPasswordResetCode,
  useResetPassword,
} from '../../features/auth/hooks/usePasswordReset';
import {
  normalizeEmail,
  validateEmail,
  validatePassword,
  validatePasswordConfirm,
  validateVerificationCode,
} from '../../features/auth/validation';

interface PasswordResetErrors {
  email?: string;
  code?: string;
  password?: string;
  passwordConfirm?: string;
}

/** 다시 받기까지 기다리는 시간. 메일이 늦는 동안 몇 번이고 눌러 같은 메일을 쌓지 않게 합니다. */
const resendCooldownSeconds = 30;

export function PasswordResetPage() {
  const navigate = useNavigate();
  const codeMutation = useRequestPasswordResetCode();
  const resetMutation = useResetPassword();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [errors, setErrors] = useState<PasswordResetErrors>({});
  const [formError, setFormError] = useState<string>();
  /** 인증번호를 보낸 주소입니다. 비어 있으면 아직 보내지 않은 것입니다. */
  const [sentTo, setSentTo] = useState('');
  const [cooldown, setCooldown] = useState(0);

  const normalizedEmail = normalizeEmail(email);
  /*
   * 보낸 뒤에 주소를 고치면, 손에 든 인증번호는 지금 칸에 적힌 주소의 것이 아닙니다.
   * 그래서 보낸 표시를 거두고 단추도 다시 눌리는 상태로 돌아갑니다.
   */
  const sentToCurrent = Boolean(sentTo) && sentTo === normalizedEmail;

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((left) => left - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  const sendCode = async () => {
    const message = validateEmail(email);
    setErrors((current) => ({ ...current, email: message }));
    if (message) return;

    setFormError(undefined);
    try {
      await codeMutation.mutateAsync(email);
      setSentTo(normalizedEmail);
      setCooldown(resendCooldownSeconds);
    } catch (error) {
      /*
       * 보내지 못했으면 보낸 표시를 남기지 않습니다. 오지 않을 메일을 기다리게 하는 대신
       * 다시 눌러 볼 수 있어야 해서, 기다리는 시간도 걸지 않습니다.
       */
      setSentTo('');
      setFormError(describeAuthError(error, '인증번호를 보내지 못했습니다. 잠시 후 다시 시도해 주세요.'));
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: PasswordResetErrors = {
      email: validateEmail(email),
      code: validateVerificationCode(code),
      password: validatePassword(password),
      passwordConfirm: validatePasswordConfirm(password, passwordConfirm),
    };
    setErrors(nextErrors);
    setFormError(undefined);
    if (Object.values(nextErrors).some(Boolean)) return;

    try {
      await resetMutation.mutateAsync({ email, code, password });
      /*
       * 바꾼 것으로 로그인까지 시키지는 않습니다. 새 비밀번호를 한 번 직접 넣어 보는 편이,
       * 방금 정한 것이 무엇이었는지 손에 남습니다.
       */
      showToast({ message: '비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요.', type: 'success' });
      navigate('/login', { replace: true });
    } catch (error) {
      setFormError(describeAuthError(error, '비밀번호를 바꾸지 못했습니다. 잠시 후 다시 시도해 주세요.'));
    }
  };

  const busy = codeMutation.isPending || resetMutation.isPending;

  const sendLabel = (() => {
    if (codeMutation.isPending) return '보내는 중…';
    if (cooldown > 0) return `${cooldown}초 후 재전송`;
    return sentToCurrent ? '다시 받기' : '인증번호 받기';
  })();

  return (
    <AuthScene className="password-reset-scene">
      <div className="auth-scene-card password-reset-card">

        <h2>비밀번호 재설정</h2>

        <p className="auth-scene-card-lead">이메일 인증 후 새로운 비밀번호를 설정해주세요.</p>

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
            placeholder="이메일을 입력해주세요."
            autoComplete="email"
            error={errors.email}
            disabled={busy}
          />
          <AuthSceneField
            label="인증번호"
            icon={<CheckCircleIcon />}
            value={code}
            onChange={(value) => {
              setCode(value);
              setErrors((current) => (current.code ? { ...current, code: undefined } : current));
            }}
            placeholder="인증번호를 입력해주세요."
            autoComplete="one-time-code"
            error={errors.code}
            /* 보내기 전에는 비워 둡니다. 안내를 미리 깔아 두면 카드가 그만큼 길어집니다. */
            hint={sentToCurrent ? '인증번호를 보냈습니다. 메일함을 확인해 주세요.' : undefined}
            disabled={busy}
            action={(
              <button
                type="button"
                className="password-reset-send"
                onClick={sendCode}
                disabled={busy || cooldown > 0}
              >
                {sendLabel}
              </button>
            )}
          />
          <AuthSceneField
            label="새 비밀번호"
            icon={<LockIcon />}
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="영문, 숫자, 특수문자를 포함해 8자 이상"
            autoComplete="new-password"
            error={errors.password}
            hint={<PasswordChecklist password={password} />}
            disabled={busy}
          />
          <AuthSceneField
            label="비밀번호 확인"
            icon={<LockIcon />}
            type="password"
            value={passwordConfirm}
            onChange={setPasswordConfirm}
            onBlur={() => setErrors((current) => ({ ...current, passwordConfirm: validatePasswordConfirm(password, passwordConfirm) }))}
            placeholder="비밀번호를 한 번 더 입력해주세요."
            autoComplete="new-password"
            error={errors.passwordConfirm}
            disabled={busy}
          />

          {formError && <p className="auth-scene-alert" role="alert">{formError}</p>}

          <button className="auth-scene-submit" type="submit" disabled={busy}>
            {resetMutation.isPending && <Spinner size="small" />}
            {resetMutation.isPending ? '바꾸는 중…' : '비밀번호 재설정'}
          </button>
        </form>

        {/* 시안의 보조 단추입니다. 같은 자리의 '이미 계정이 있으신가요?' 줄과 갈 곳이 같아 하나만 둡니다. */}
        <Link className="password-reset-back" to="/login">로그인으로 돌아가기</Link>
      </div>
    </AuthScene>
  );
}
