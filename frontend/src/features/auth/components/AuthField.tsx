import { useId, useState } from 'react';
import type { ReactNode } from 'react';

interface AuthFieldProps {
  label: string;
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

export function AuthField({
  label, type = 'text', value, onChange, onBlur, placeholder, autoComplete, error, hint, disabled, action,
}: AuthFieldProps) {
  const fieldId = useId();
  const noteId = `${fieldId}-note`;
  // 비밀번호는 오타를 확인할 수 있게 잠깐 드러낼 수 있습니다.
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === 'password';
  const note = error ?? hint;

  return (
    <div className={`auth-field${error ? ' is-invalid' : ''}`}>
      <label className="auth-label" htmlFor={fieldId}>{label}</label>
      <div className="auth-input">
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
          aria-describedby={note ? noteId : undefined}
        />
        {isPassword && (
          <button
            type="button"
            className="auth-reveal"
            aria-pressed={revealed}
            aria-label={revealed ? '비밀번호 숨기기' : '비밀번호 보기'}
            onClick={() => setRevealed((current) => !current)}
          >
            {revealed ? '숨기기' : '보기'}
          </button>
        )}
        {action}
      </div>
      {/* 확인 결과는 눈으로만 보이면 안 되어서, 오류는 alert로 안내는 status로 읽히게 합니다. */}
      {note && (
        <div
          className={`auth-note${error ? ' is-error' : ''}`}
          id={noteId}
          role={error ? 'alert' : 'status'}
        >
          {note}
        </div>
      )}
    </div>
  );
}
