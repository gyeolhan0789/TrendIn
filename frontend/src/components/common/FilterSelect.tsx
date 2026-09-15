interface FilterSelectProps {
  value: string;
  options: { value: string; label: string }[];
  /** 칸 앞에 붙는 이름. 없으면 고른 값만 보여 주는 홑 칸이 됩니다. */
  label?: string;
  ariaLabel?: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  title?: string;
}

/** 새 시안의 드롭다운 한 칸. 트렌드 탐색의 필터줄과 관심 키워드의 도구줄이 같은 모양을 씁니다. */
export function FilterSelect({ value, options, label, ariaLabel, onChange, disabled = false, title }: FilterSelectProps) {
  const field = (
    <div className={`trendin-select${disabled ? ' is-disabled' : ''}`} title={title}>
      <select value={value} disabled={disabled} aria-label={ariaLabel ?? label} onChange={(event) => onChange?.(event.target.value)}>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
    </div>
  );

  if (!label) return field;

  return (
    <div className="trendin-filter">
      <span className="trendin-filter-label">{label}</span>
      {field}
    </div>
  );
}
