import type { DomainOption } from '../types/onboarding';

interface DomainChoiceProps {
  option: DomainOption;
  selected: boolean;
  disabled?: boolean;
  onToggle: (domain: string) => void;
}

/*
 * 분야는 배포 전에는 늘어나지 않지만 코드를 박아 두지 않습니다. 서버가 준 이름을 그대로 쓰고,
 * 아이콘 같은 분야별 장식도 두지 않아야 분야가 늘어도 화면을 고치지 않습니다.
 */
export function DomainChoice({ option, selected, disabled, onToggle }: DomainChoiceProps) {
  return (
    <button
      type="button"
      className={`onboarding-choice${selected ? ' is-selected' : ''}`}
      role="checkbox"
      aria-checked={selected}
      disabled={disabled}
      onClick={() => onToggle(option.domain)}
    >
      <span className="onboarding-choice-mark" aria-hidden="true">
        {selected && (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
        )}
      </span>
      <strong>{option.name}</strong>
      <small>{option.domain}</small>
    </button>
  );
}
