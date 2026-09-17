import { useEffect, useId, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { nextIndex } from '../../utils/listCursor';

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

/**
 * 새 시안의 드롭다운 한 칸. 트렌드 탐색의 필터줄, 관심 키워드와 저장한 트렌드의 도구줄이
 * 모두 이 칸을 씁니다.
 *
 * 브라우저가 그리는 select 목록은 화면마다 생김새가 달라 시안과 맞출 수 없습니다. 그래서
 * 목록은 직접 그려, 검색어 목록과 같은 흰 카드로 내려오게 합니다.
 */
export function FilterSelect({ value, options, label, ariaLabel, onChange, disabled = false, title }: FilterSelectProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const box = useRef<HTMLDivElement>(null);
  const name = ariaLabel ?? label;
  const selected = options.find((option) => option.value === value);

  const close = () => {
    setOpen(false);
    setActiveIndex(-1);
  };

  // 열 때는 지금 고른 값에 자리를 맞춰 둡니다. 위아래 키가 거기서부터 움직입니다.
  const show = () => {
    setActiveIndex(options.findIndex((option) => option.value === value));
    setOpen(true);
  };

  // 바깥을 누르면 닫습니다. click은 목록의 줄이 사라진 뒤에 와서 pointerdown을 씁니다.
  useEffect(() => {
    if (!open) return;
    const away = (event: PointerEvent) => {
      if (!box.current?.contains(event.target as Node)) close();
    };
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  }, [open]);

  const choose = (option: { value: string }) => {
    close();
    if (option.value !== value) onChange?.(option.value);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Escape') {
      close();
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (open && activeIndex >= 0) choose(options[activeIndex]);
      else show();
      return;
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;

    event.preventDefault();
    if (!open) {
      show();
      return;
    }
    setActiveIndex((current) => nextIndex(current, options.length, event.key === 'ArrowDown'));
  };

  // 같은 칸이 한 쪽에 여럿 서므로 이름은 React 가 겹치지 않게 지어 줍니다.
  const menuId = useId();
  const field = (
    <div className={`trendin-select${disabled ? ' is-disabled' : ''}${open ? ' is-open' : ''}`} title={title} ref={box}>
      <button
        type="button"
        className="trendin-select-value"
        disabled={disabled}
        aria-label={name}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-activedescendant={open && activeIndex >= 0 ? `${menuId}-${activeIndex}` : undefined}
        onClick={() => (open ? close() : show())}
        onKeyDown={handleKeyDown}
      >
        <span className="trendin-select-current">{selected?.label ?? value}</span>
        {/*
          * 고른 값에 따라 칸 너비가 들썩이지 않도록, 보이지 않는 자리에 모든 값을 겹쳐 둡니다.
          * 칸은 그중 가장 긴 값에 맞춰 서고, 무엇을 고르든 그 너비 그대로 머뭅니다.
          */}
        <span className="trendin-select-sizer" aria-hidden="true">
          {options.map((option) => <span key={option.value}>{option.label}</span>)}
        </span>
      </button>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>

      {open && (
        <ul className="trendin-select-menu" id={menuId} role="listbox" aria-label={name}>
          {options.map((option, index) => (
            <li
              key={option.value}
              id={`${menuId}-${index}`}
              role="option"
              aria-selected={option.value === value}
              className={`trendin-select-row${index === activeIndex ? ' is-active' : ''}${option.value === value ? ' is-selected' : ''}`}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(option)}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
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
