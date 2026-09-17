import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Spinner } from '../../components/common/Spinner';
import { showToast } from '../../components/common/toast';
import { AuthScene } from '../../features/auth/components/AuthScene';
import { AuthSceneField } from '../../features/auth/components/AuthSceneField';
import { CheckIcon, LockIcon, MailIcon, UserIcon } from '../../features/auth/components/authIcons';
import { PasswordChecklist } from '../../features/auth/components/PasswordChecklist';
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
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState<SignUpErrors>({});
  const [formError, setFormError] = useState<string>();
  /** 중복확인을 누른 주소입니다. 비어 있으면 아직 확인하지 않은 것입니다. */
  const [checkedEmail, setCheckedEmail] = useState('');

  // 가입 직후 자동 로그인으로 세션이 생기므로, 로그인 화면과 같은 이유로 진입 시점만 봅니다.
  const [enteredLoggedIn] = useState(() => Boolean(getAuthSession()));

  const normalizedEmail = normalizeEmail(email);
  // 가입이 시작되면 캐시를 비우는데, 그때 이 질의가 되살아나 쓸데없이 한 번 더 확인하러 갑니다.
  const availabilityQuery = useEmailAvailability(checkedEmail, Boolean(checkedEmail) && signUpMutation.isIdle);
  // 이메일을 고치면 앞서 받은 확인 결과는 지금 값의 것이 아니어서, 버튼이 다시 눌리는 상태로 돌아갑니다.
  const checkedCurrent = checkedEmail === normalizedEmail;
  const available = checkedCurrent ? availabilityQuery.data : undefined;
  const checkingEmail = checkedCurrent && availabilityQuery.isFetching;
  // 다시 부르는 중이면 아직 실패라고 하지 않습니다. 앞선 실패가 남아 있을 뿐입니다.
  const checkFailed = checkedCurrent && availabilityQuery.isError && !checkingEmail;

  const takenError = available === false ? '이미 가입된 이메일입니다.' : undefined;
  const emailError = errors.email ?? takenError;

  // 칸 아래 한 줄은 확인을 마쳤을 때만 씁니다. 평소에 안내를 깔아 두면 카드가 그만큼 길어집니다.
  const emailHint = (() => {
    if (checkingEmail) return '이메일을 확인하는 중…';
    if (available === true) {
      return <span className="signup-ok"><CheckIcon />사용할 수 있는 이메일입니다.</span>;
    }
    // 확인이 실패하면 실패했다고 말합니다. 못 한 일을 한 것처럼 넘기지 않습니다.
    if (checkFailed) {
      return <span className="signup-fail">이메일을 확인하지 못했습니다. 다시 시도해 주세요.</span>;
    }
    return undefined;
  })();

  /** 중복확인 버튼이 부르는 경로입니다. 형식이 틀리면 서버를 부르지 않고 그 자리에서 알려 줍니다. */
  const checkEmail = () => {
    const message = validateEmail(email);
    setErrors((current) => ({ ...current, email: message }));
    if (message) {
      setCheckedEmail('');
      return;
    }
    /*
     * 앞서 확인이 실패한 주소를 다시 누르는 경우입니다. 확인한 주소가 그대로라 상태가 바뀌지 않고,
     * 실패 결과도 staleTime 동안 캐시에 남아 있어 그냥 두면 질의가 다시 돌지 않습니다.
     */
    if (checkedEmail === normalizedEmail) {
      void availabilityQuery.refetch();
      return;
    }
    setCheckedEmail(normalizedEmail);
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
    /*
     * 이미 쓰인 이메일인 줄 알면서 보내지 않습니다. 다만 확인을 누르지 않았다고 막지는 않습니다.
     * 확인은 안내이고, 중복 판정은 가입 응답의 409가 합니다. 확인이 실패하는 날에도 가입은 되어야 합니다.
     */
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

  /*
   * 답을 받은 주소는 다시 누를 이유가 없어 잠급니다. 다만 확인이 실패했을 때(null)는 잠그지
   * 않습니다. 서버가 잠깐 답하지 못한 것일 수 있는데, 그때 잠겨 버리면 다시 눌러 볼 길이 없습니다.
   */
  const checkDisabled = signUpMutation.isPending || checkingEmail || (checkedCurrent && typeof available === 'boolean');

  return (
    <AuthScene>
      <div className="auth-scene-card">
        <h2>회원가입</h2>
        <p className="auth-scene-card-lead">TrendIn과 함께 더 빠르게,<br />나만의 관심 트렌드를 시작해보세요.</p>

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
            error={emailError}
            hint={emailHint}
            disabled={signUpMutation.isPending}
            action={(
              /* 확인을 마치면 버튼이 그대로 결과 표시가 됩니다. 다시 누를 일이 없어 잠겨 있습니다. */
              <button
                type="button"
                className={`signup-check${available === true ? ' is-done' : ''}`}
                onClick={checkEmail}
                disabled={checkDisabled}
              >
                {checkingEmail && '확인 중…'}
                {!checkingEmail && available === true && <><CheckIcon />확인</>}
                {!checkingEmail && available !== true && '중복확인'}
              </button>
            )}
          />
          <AuthSceneField
            label="비밀번호"
            icon={<LockIcon />}
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="영문, 숫자, 특수문자를 포함해 8자 이상"
            autoComplete="new-password"
            error={errors.password}
            hint={<PasswordChecklist password={password} />}
            disabled={signUpMutation.isPending}
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
            disabled={signUpMutation.isPending}
          />
          <AuthSceneField
            label="닉네임"
            icon={<UserIcon />}
            value={nickname}
            onChange={setNickname}
            onBlur={() => setErrors((current) => ({ ...current, nickname: validateNickname(nickname) }))}
            placeholder="닉네임을 입력해주세요. (2~30자)"
            autoComplete="nickname"
            error={errors.nickname}
            disabled={signUpMutation.isPending}
          />

          <label className="signup-agree">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(event) => setAgreed(event.target.checked)}
              disabled={signUpMutation.isPending}
            />
            {/* 약관 본문은 아직 없어서, 링크 대신 글자만 짚어 둡니다. 생기면 여기에 겁니다. */}
            <span><b>이용약관</b> 및 <b>개인정보처리방침</b>에 동의합니다.</span>
          </label>

          {formError && <p className="auth-scene-alert" role="alert">{formError}</p>}

          <button className="auth-scene-submit" type="submit" disabled={!agreed || signUpMutation.isPending}>
            {signUpMutation.isPending && <Spinner size="small" />}
            {signUpMutation.isPending ? '가입하는 중…' : '회원가입'}
          </button>
        </form>

        <p className="auth-scene-card-foot">이미 계정이 있으신가요? <Link to="/login">로그인</Link></p>
      </div>
    </AuthScene>
  );
}
