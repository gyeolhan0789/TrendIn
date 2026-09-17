import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useKeywordSearch } from './useKeywordSearch';
import { nextSuggestIndex } from '../keywordSuggest';
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import type { KeywordSearchItem } from '../types/keyword';

/** 글자를 칠 때마다 보내지 않고, 잠시 멈춘 뒤의 값으로만 찾습니다. */
const SEARCH_DELAY_MS = 250;
/** 자동완성은 고르는 자리지 목록을 보는 자리가 아니라, 앞쪽 몇 개만 내어 줍니다. */
const SUGGEST_LIMIT = 8;

export type KeywordSuggestStatus = 'loading' | 'error' | 'empty' | 'ready';

/**
 * 검색 상자에 붙는 자동완성입니다. 무엇을 보여 줄지만 정하고, 고른 뒤에 어디로 갈지는
 * 부르는 화면이 정합니다. 트렌드에 오르지 않은 키워드도 서버가 함께 내려주므로
 * 목록에서 빼지 않고, 트렌드가 없다는 사실을 같이 보여 줍니다.
 */
export function useKeywordSuggest(query: string, onSelect: (item: KeywordSearchItem) => void) {
  const trimmed = query.trim();
  const debounced = useDebouncedValue(trimmed, SEARCH_DELAY_MS);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const box = useRef<HTMLElement>(null);

  const searchQuery = useKeywordSearch(debounced);
  const items = useMemo(
    () => (searchQuery.data?.items ?? []).slice(0, SUGGEST_LIMIT),
    [searchQuery.data],
  );

  const visible = open && trimmed.length > 0;
  // 멈추기를 기다리는 동안 이전 검색어의 결과를 들고 있어, 그때도 '찾는 중'으로 둡니다.
  const waiting = searchQuery.isLoading || debounced !== trimmed;
  const status: KeywordSuggestStatus = waiting
    ? 'loading'
    : searchQuery.isError ? 'error' : items.length === 0 ? 'empty' : 'ready';

  const hide = useCallback(() => {
    setOpen(false);
    setActiveIndex(-1);
  }, []);

  const show = useCallback(() => setOpen(true), []);

  // 검색어가 바뀌면 골라 둔 자리는 다른 줄을 가리키게 되므로 풀어 둡니다.
  useEffect(() => setActiveIndex(-1), [debounced]);

  // 바깥을 누르면 닫습니다. click은 목록의 줄이 사라진 뒤에 와서 pointerdown을 씁니다.
  useEffect(() => {
    if (!visible) return;
    const close = (event: PointerEvent) => {
      if (!box.current?.contains(event.target as Node)) hide();
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [visible, hide]);

  const select = useCallback((item: KeywordSearchItem) => {
    hide();
    onSelect(item);
  }, [hide, onSelect]);

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      hide();
      return;
    }
    if (event.key === 'Enter') {
      // 고른 줄이 없으면 막지 않습니다. 그대로 두면 지금까지처럼 이 쪽 목록을 거릅니다.
      if (!visible || activeIndex < 0) return;
      event.preventDefault();
      select(items[activeIndex]);
      return;
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;

    event.preventDefault();
    if (!visible) {
      show();
      return;
    }
    const down = event.key === 'ArrowDown';
    setActiveIndex((current) => nextSuggestIndex(current, items.length, down));
  };

  return { box, visible, items, status, activeIndex, setActiveIndex, show, hide, select, handleKeyDown };
}
