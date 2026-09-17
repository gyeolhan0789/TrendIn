import { useId, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Spinner } from '../../components/common/Spinner';
import { showToast } from '../../components/common/toast';
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

function MailIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="4" width="20" height="16" rx="3" />
      <path d="M22 7l-10 6L2 7" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="3" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
      {off && <path d="M3 3l18 18" />}
    </svg>
  );
}

interface SignUpFieldProps {
  label: string;
  icon: ReactNode;
  type?: 'text' | 'email' | 'password';
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  placeholder?: string;
  autoComplete?: string;
  /** 규칙을 어겼을 때만 채웁니다. 값이 있으면 hint 대신 이 문구를 보여줍니다. */
  error?: string;
  hint?: ReactNode;
  disabled?: boolean;
  /** 칸 안 오른쪽에 붙는 버튼. 이메일 중복확인처럼 그 칸에서 바로 하는 일에 씁니다. */
  action?: ReactNode;
}

/**
 * 시안의 아이콘 달린 입력 칸입니다. 비밀번호 칸은 눈 버튼으로 잠깐 드러낼 수 있습니다.
 *
 * 오류 문구는 칸 아래가 아니라 이름표 옆에 답니다. 아래에 달면 네 칸이 한꺼번에 틀렸을 때
 * 카드가 그만큼 길어져, 낮은 창에서 애써 없앤 스크롤이 도로 생깁니다.
 */
function SignUpField({
  label, icon, type = 'text', value, onChange, onBlur, placeholder, autoComplete, error, hint, disabled, action,
}: SignUpFieldProps) {
  const fieldId = useId();
  const errorId = `${fieldId}-error`;
  const hintId = `${fieldId}-hint`;
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === 'password';
  const describedBy = [error && errorId, hint && hintId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={`signup-field${error ? ' is-invalid' : ''}`}>
      <div className="signup-label-row">
        <label className="signup-label" htmlFor={fieldId}>{label}</label>
        {error && <span className="signup-field-error" id={errorId} role="alert">{error}</span>}
      </div>
      <div className="signup-input">
        <span className="signup-input-icon" aria-hidden="true">{icon}</span>
        <input
          id={fieldId}
          type={isPassword && revealed ? 'text' : type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          placeholder={placeholder}
          autoComplete={autoComplete}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
        {isPassword && (
          <button
            type="button"
            className="signup-reveal"
            aria-pressed={revealed}
            aria-label={revealed ? '비밀번호 숨기기' : '비밀번호 보기'}
            onClick={() => setRevealed((current) => !current)}
          >
            <EyeIcon off={revealed} />
          </button>
        )}
        {action}
      </div>
      {/* 칸 아래는 안내 자리입니다. 비밀번호 규칙처럼 늘 서 있는 줄이라 높이가 흔들리지 않습니다. */}
      {hint && <div className="signup-note" id={hintId} role="status">{hint}</div>}
    </div>
  );
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

  const takenError = available === false ? '이미 가입된 이메일입니다.' : undefined;
  const emailError = errors.email ?? takenError;

  // 칸 아래 한 줄은 확인을 마쳤을 때만 씁니다. 평소에 안내를 깔아 두면 카드가 그만큼 길어집니다.
  const emailHint = (() => {
    if (checkingEmail) return '이메일을 확인하는 중…';
    if (available === true) return '사용할 수 있는 이메일입니다.';
    // 확인에 실패하면(null) 굳이 알리지 않습니다. 중복은 가입 응답이 최종적으로 가려냅니다.
    return undefined;
  })();

  /** 중복확인 버튼이 부르는 경로입니다. 형식이 틀리면 서버를 부르지 않고 그 자리에서 알려 줍니다. */
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

  // 같은 주소를 이미 확인했으면 다시 누를 이유가 없어 버튼을 잠급니다.
  const checkDisabled = signUpMutation.isPending || checkingEmail || (checkedCurrent && available !== undefined);

  return (
    <div className="trendin-ui signup-page">
      {/* 시안의 물결 배경. 장식이라 읽히지 않게 두고 클릭도 통과시킵니다. */}
      <div className="signup-wave" aria-hidden="true">
        <svg viewBox="0 0 800 320" preserveAspectRatio="none" fill="none">
          <defs>
            <linearGradient id="signup-wave-a" x1="0" y1="0" x2="800" y2="320" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#c7d2fe" stopOpacity="0.5" />
              <stop offset="40%" stopColor="#a5b4fc" stopOpacity="0.3" />
              <stop offset="70%" stopColor="#e0e7ff" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#ddd6fe" stopOpacity="0.2" />
            </linearGradient>
            <linearGradient id="signup-wave-b" x1="0" y1="80" x2="800" y2="280" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.15" />
              <stop offset="50%" stopColor="#a78bfa" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#c4b5fd" stopOpacity="0.08" />
            </linearGradient>
          </defs>
          <path d="M0 200 Q100 140 200 180 T400 150 T600 190 T800 160 L800 320 L0 320Z" fill="url(#signup-wave-a)" />
          <path d="M0 230 Q150 170 300 210 T500 180 T700 220 T800 190 L800 320 L0 320Z" fill="url(#signup-wave-b)" />
          <path d="M0 260 Q120 220 250 250 T450 230 T650 260 T800 240 L800 320 L0 320Z" fill="#e0e7ff" fillOpacity="0.3" />
        </svg>
      </div>

      <header className="signup-header">
        <Link className="signup-brand" to="/" aria-label="TrendIn 홈">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" fill="#4F46E5" stroke="#4F46E5" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          TrendIn
        </Link>
        <Link className="signup-home" to="/">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M19 12H5M12 5l-7 7 7 7" />
          </svg>
          홈으로
        </Link>
      </header>

      <div className="signup-main">
        <section className="signup-hero">
          <p className="signup-hero-eyebrow">REAL-TIME TREND INSIGHTS</p>
          <h1>지금,<br />세상을 움직이는<br /><span>트렌드</span>를 담다</h1>
          <p className="signup-hero-lead">수많은 데이터 속에서 중요한 흐름을 찾아,<br />더 빠르고, 더 깊이 있게.</p>

          <div className="signup-hero-stat">
            <div>
              <p className="signup-hero-stat-value">+284%</p>
              <p className="signup-hero-stat-label">언급량 증가</p>
            </div>
            <span className="signup-hero-stat-mark" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2.5" strokeLinecap="round">
                <path d="M7 17l5-5 4 4 5-6" />
                <path d="M17 10h5v5" />
              </svg>
            </span>
          </div>

          <ul className="signup-hero-features">
            <li>
              <span className="signup-hero-feature-mark" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round">
                  <rect x="3" y="12" width="4" height="9" rx="1" />
                  <rect x="10" y="7" width="4" height="14" rx="1" />
                  <rect x="17" y="3" width="4" height="18" rx="1" />
                </svg>
              </span>
              <strong>실시간 트렌드 분석</strong>
              <span>지금 이 순간의 변화를 포착</span>
            </li>
            <li>
              <span className="signup-hero-feature-mark" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z" />
                </svg>
              </span>
              <strong>AI 기반 인사이트</strong>
              <span>데이터가 만드는 새로운 시선</span>
            </li>
            <li>
              <span className="signup-hero-feature-mark" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round">
                  <path d="M4 8h16M4 12h16M4 16h16" />
                </svg>
              </span>
              <strong>다양한 카테고리</strong>
              <span>관심 있는 모든 트렌드 한눈에</span>
            </li>
          </ul>

          <div className="signup-hero-foot">
            <div>
              <p>지금도,<br />새로운 트렌드가 만들어지고 있어요.</p>
              <span className="signup-hero-progress" aria-hidden="true"><i /></span>
            </div>
            <p className="signup-hero-side">DISCOVER<br />ANALYZE<br />BE INSPIRED</p>
          </div>
        </section>

        <section className="signup-panel">
          <div className="signup-card">
            <h2>회원가입</h2>
            <p className="signup-card-lead">TrendIn과 함께 더 빠르게,<br />나만의 관심 트렌드를 시작해보세요.</p>

            <form className="signup-form" onSubmit={submit} noValidate>
              <SignUpField
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
                  <button type="button" className="signup-check" onClick={checkEmail} disabled={checkDisabled}>
                    {checkingEmail ? '확인 중…' : '중복확인'}
                  </button>
                )}
              />
              <SignUpField
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
              <SignUpField
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
              <SignUpField
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

              {formError && <p className="signup-alert" role="alert">{formError}</p>}

              <button className="signup-submit" type="submit" disabled={!agreed || signUpMutation.isPending}>
                {signUpMutation.isPending && <Spinner size="small" />}
                {signUpMutation.isPending ? '가입하는 중…' : '회원가입'}
              </button>
            </form>

            <div className="signup-divider"><i />또는<i /></div>
            {/* 소셜 로그인 API는 계약만 있고 제공자가 정해지지 않아, 누를 수 없는 버튼 대신 한 줄로 밝힙니다. */}
            <p className="signup-social-note">소셜 로그인은 준비 중입니다.</p>

            <p className="signup-footer">이미 계정이 있으신가요? <Link to="/login">로그인</Link></p>
          </div>
        </section>
      </div>
    </div>
  );
}
