import { splitMatch } from '../keywordSuggest';
import { formatGrowth } from '../trendFormat';
import type { KeywordSuggestStatus } from '../hooks/useKeywordSuggest';
import type { KeywordSearchItem } from '../types/keyword';

/** 검색어와 겹치는 자리를 굵게 보여 줍니다. */
function Marked({ text, query }: { text: string; query: string }) {
  const [before, hit, after] = splitMatch(text, query);
  if (!hit) return <>{text}</>;
  return <>{before}<mark>{hit}</mark>{after}</>;
}

/**
 * 줄 오른쪽에 붙는 설명입니다. 아직 트렌드에 오르지 않은 키워드는 상세가 없고,
 * 이전 구간이 없으면 증감률도 비어 있어 그 자리에 숫자를 지어내지 않습니다.
 */
function describeSuggestion(item: KeywordSearchItem) {
  if (item.trendId === null) return '트렌드 없음';
  if (item.growthRate === null) return '상세 보기';
  return `${formatGrowth(item.growthRate)} · 상세 보기`;
}

interface KeywordSuggestMenuProps {
  /** 입력칸의 aria-controls·aria-activedescendant 가 가리킬 이름입니다. */
  id: string;
  query: string;
  items: KeywordSearchItem[];
  status: KeywordSuggestStatus;
  activeIndex: number;
  onHover: (index: number) => void;
  onSelect: (item: KeywordSearchItem) => void;
}

/** 검색 상자 아래에 뜨는 검색어 목록입니다. 무엇을 고르는지는 useKeywordSuggest 가 쥐고 있습니다. */
export function KeywordSuggestMenu({
  id, query, items, status, activeIndex, onHover, onSelect,
}: KeywordSuggestMenuProps) {
  if (status !== 'ready') {
    return (
      <div className="keyword-suggest" id={id}>
        <p className="keyword-suggest-none" role="status">
          {status === 'loading' && '찾는 중…'}
          {status === 'error' && '키워드를 찾지 못했습니다.'}
          {status === 'empty' && '검색어와 맞는 키워드가 없습니다.'}
        </p>
      </div>
    );
  }

  return (
    <div className="keyword-suggest">
      <ul className="keyword-suggest-list" id={id} role="listbox" aria-label="검색어 목록">
        {items.map((item, index) => (
          <li
            key={item.keywordId}
            id={`${id}-${index}`}
            role="option"
            aria-selected={index === activeIndex}
            className={`keyword-suggest-row${index === activeIndex ? ' is-active' : ''}`}
            onMouseEnter={() => onHover(index)}
            onClick={() => onSelect(item)}
          >
            <span className="keyword-suggest-name">
              <strong><Marked text={item.keyword} query={query} /></strong>
              <small>{item.domain.name}</small>
            </span>
            <span className="keyword-suggest-meta">{describeSuggestion(item)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
