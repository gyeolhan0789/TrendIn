import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { EyeIcon } from './authIcons';

interface AuthSceneFieldProps {
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
  /** 칸 옆에 붙는 버튼. 이메일 중복확인처럼 그 칸에서 바로 하는 일에 씁니다. */
  action?: ReactNode;
}

/**
 * 시안의 아이콘 달린 입력 칸입니다. 비밀번호 칸은 눈 버튼으로 잠깐 드러낼 수 있습니다.
 *
 * 오류 문구는 칸 아래가 아니라 이름표 옆에 답니다. 아래에 달면 여러 칸이 한꺼번에 틀렸을 때
 * 카드가 그만큼 길어져, 낮은 창에서 애써 없앤 스크롤이 도로 생깁니다.
 */
export function AuthSceneField({
  label, icon, type = 'text', value, onChange, onBlur, placeholder, autoComplete, error, hint, disabled, action,
}: AuthSceneFieldProps) {
  const fieldId = useId();
  const errorId = `${fieldId}-error`;
  const hintId = `${fieldId}-hint`;
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === 'password';
  const describedBy = [error && errorId, hint && hintId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={`auth-scene-field${error ? ' is-invalid' : ''}`}>
      <div className="auth-scene-label-row">
        <label className="auth-scene-label" htmlFor={fieldId}>{label}</label>
        {error && <span className="auth-scene-field-error" id={errorId} role="alert">{error}</span>}
      </div>
      <div className="auth-scene-input-row">
        <div className="auth-scene-input">
          <span className="auth-scene-input-icon" aria-hidden="true">{icon}</span>
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
              className="auth-scene-reveal"
              aria-pressed={revealed}
              aria-label={revealed ? '비밀번호 숨기기' : '비밀번호 보기'}
              onClick={() => setRevealed((current) => !current)}
            >
              <EyeIcon off={revealed} />
            </button>
          )}
        </div>
        {/* 중복확인처럼 칸에 딸린 단추는 칸 밖 오른쪽에 세웁니다. 그만큼 입력 칸이 좁아집니다. */}
        {action}
      </div>
      {/* 칸 아래는 안내 자리입니다. 비밀번호 규칙처럼 늘 서 있는 줄이라 높이가 흔들리지 않습니다. */}
      {hint && <div className="auth-scene-note" id={hintId} role="status">{hint}</div>}
    </div>
  );
}
