import { passwordRules } from '../validation';

interface PasswordChecklistProps {
  password: string;
}

/** 어느 조건이 모자란지 입력하는 동안 보여줍니다. 제출한 뒤에야 알게 되면 늦습니다. */
export function PasswordChecklist({ password }: PasswordChecklistProps) {
  return (
    <ul className="auth-checklist">
      {passwordRules.map((rule) => {
        const met = rule.test(password);
        return (
          <li className={met ? 'is-met' : ''} key={rule.label}>
            <span aria-hidden="true">{met ? '✓' : '·'}</span>
            {rule.label}
            <span className="sr-only">{met ? ' 충족' : ' 미충족'}</span>
          </li>
        );
      })}
    </ul>
  );
}
