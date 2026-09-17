interface ToggleSwitchProps {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  /** 시안의 큰 스위치(전체 알림)와 줄마다 서는 작은 스위치를 같은 부품으로 그립니다. */
  size?: 'sm' | 'md';
}

/**
 * 켜고 끄는 스위치입니다. 시안은 <div>에 클릭을 달았지만, 키보드로도 닿아야 하고
 * 읽어 주는 장치가 상태를 알아야 해서 role="switch" 를 단 버튼으로 세웁니다.
 */
export function ToggleSwitch({ checked, label, onChange, disabled = false, size = 'sm' }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={`mypage-switch mypage-switch--${size}${checked ? ' is-on' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span aria-hidden="true" />
    </button>
  );
}
