import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { AuthScene } from '../../features/auth/components/AuthScene';
import { AuthSceneField } from '../../features/auth/components/AuthSceneField';
import { LockIcon, MailIcon } from '../../features/auth/components/authIcons';
import { PasswordChecklist } from '../../features/auth/components/PasswordChecklist';
import {
  validateEmail,
  validatePassword,
  validatePasswordConfirm,
} from '../../features/auth/validation';

interface PasswordResetErrors {
  email?: string;
  password?: string;
  passwordConfirm?: string;
}


export function PasswordResetPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [errors, setErrors] = useState<PasswordResetErrors>({});
  const [formError, setFormError] = useState<string>();
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: PasswordResetErrors = {
      email: validateEmail(email),
      password: validatePassword(password),
      passwordConfirm: validatePasswordConfirm(password, passwordConfirm),
    };
    setErrors(nextErrors);
    setFormError(undefined);
    if (Object.values(nextErrors).some(Boolean)) return;

    setFormError('현재 비밀번호 재설정 기능은 준비 중입니다.');
  };

  return (
    <AuthScene className="password-reset-scene">
      <div className="auth-scene-card password-reset-card">

        <h2>비밀번호 재설정</h2>

        <p className="auth-scene-card-lead">비밀번호 재설정 기능은 준비 중입니다.</p>

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
          />

          {formError && <p className="auth-scene-alert" role="alert">{formError}</p>}

          <button className="auth-scene-submit" type="submit">
            비밀번호 재설정
          </button>
        </form>

        {/* 시안의 보조 단추입니다. 같은 자리의 '이미 계정이 있으신가요?' 줄과 갈 곳이 같아 하나만 둡니다. */}
        <Link className="password-reset-back" to="/login">로그인으로 돌아가기</Link>
      </div>
    </AuthScene>
  );
}

