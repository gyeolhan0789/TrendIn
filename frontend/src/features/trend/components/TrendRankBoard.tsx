import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BookmarkButton } from '../../savedTrend/components/BookmarkButton';
import { useTrends } from '../hooks/useTrends';
import { useTrendDetailLink } from '../trendDetailLink';
import { formatCount, formatGrowth } from '../trendFormat';
import type { PeriodCode } from '../../../constants/filterCodes';
import type { Trend, TrendType } from '../types/trend';

/** 한 판에 보여 줄 기본 개수. 1위 한 장 + 2~5위 네 줄이라 시안의 2열 4행이 그대로 찹니다. */
export const TOP_COUNT = 5;

interface BoardLook {
  title: string;
  lead: string;
  /** 머리 띠와 순위 색에 쓰는 색 갈래입니다. */
  tone: 'indigo' | 'emerald' | 'rose';
  /** 앞머리 아이콘. 머리글 배지와 1위 카드의 순위 알약이 같은 그림을 씁니다. */
  icon: string;
  /** 1위 카드의 큰 숫자가 무엇을 센 값인지 알려 주는 한마디입니다. */
  measure: string;
}

/** 갈래마다 이름·설명·색이 다릅니다. 순위를 매기는 기준도 달라 크게 쓰는 값이 갈립니다. */
const looks: Record<TrendType, BoardLook> = {
  CURRENT: { title: '인기 트렌드', lead: `언급량 기준 TOP ${TOP_COUNT}`, tone: 'indigo', measure: '언급량', icon: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z' },
  NEW: { title: '신규 트렌드', lead: '최근 새로 등장한 키워드', tone: 'emerald', measure: '언급량 증가율', icon: 'M12 5v14M5 12h14' },
  RISING: { title: '급상승 트렌드', lead: `증가율 기준 TOP ${TOP_COUNT}`, tone: 'rose', measure: '언급량 증가율', icon: 'M13 3L4 14h7l-2 7 9-11h-7l2-7z' },
};

/** 갈래가 무엇으로 줄을 세웠는지. 그 값을 한 줄의 오른쪽 끝과 1위 카드의 큰 숫자에 씁니다. */
function headline(trend: Trend, type: TrendType) {
  /* 언급량은 %와 달리 단위가 없어 맨숫자로 뜹니다. 세는 단위를 붙여야 무엇을 센 값인지 읽힙니다. */
  if (type === 'CURRENT') return `${formatCount(trend.mentionCount)}건`;
  if (type === 'NEW' && trend.growthRate === null) return 'NEW';
  return formatGrowth(trend.growthRate);
}

function BoardIcon({ path, size }: { path: string; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

/**
 * 물결이 지나는 길입니다. 왼쪽 위에서 내려와 가운데에서 골을 찍고 오른쪽으로 다시 올라가는 S자로,
 * 뷰박스(0~320) 밖인 -40 과 360 에서 시작하고 끝나 카드 좌우 끝에서 잘린 티가 나지 않습니다.
 */
const WAVE_CURVE = [14, 30, 84, 120, 156, 92, 54];

/**
 * 같은 길을 dy 만큼 내려 그린 띠 하나. 위 모서리와 아래 모서리가 같은 곡선이라 굵기가 고르고,
 * 여러 장을 조금씩 겹쳐 쌓으면 층이 아니라 한 줄기가 접힌 결처럼 읽힙니다.
 */
function waveRibbon(dy: number, thickness: number) {
  const [a, b, c, d, e, f, g] = WAVE_CURVE.map((y) => y + dy);
  const t = thickness;
  return `M-40 ${a}C50 ${b} 110 ${c} 176 ${d}C240 ${e} 300 ${f} 360 ${g}`
    + `L360 ${g + t}C300 ${f + t} 240 ${e + t} 176 ${d + t}C110 ${c + t} 50 ${b + t} -40 ${a + t}Z`;
}

/**
 * 1위 카드에 깔리는 물결입니다. 그림 파일이 아니라 그려 넣는 이유는 색 때문입니다.
 *
 * 판마다 색이 다른데, 물결을 그림으로 두면 한 벌 색에 묶여 신규·급상승 판에서 겉돕니다.
 * 두 색은 판이 CSS 변수로 내려 주고, 왼쪽에서 오른쪽으로 건너가며 섞입니다. 변수는 표현 속성으로는
 * 읽히지 않아 인라인 style 로 넘깁니다. 그러데이션 id 는 한 화면에 세 판이 같이 떠 있어 갈래로 갈라 둡니다.
 */
function HeroWave({ type }: { type: TrendType }) {
  const id = `rank-wave-${type}`;
  return (
    <svg className="rank-hero-wave" viewBox="0 0 320 200" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        {/*
          * 글은 모두 카드 왼쪽에 서므로 물결은 오른쪽에서 짙어집니다. 칸을 잘라 옮기는 대신 색을
          * 치우치게 해서 옮깁니다. 왼쪽 끝을 0 으로 빼 두면 카드 왼쪽에서는 아무것도 그리지 않은 것과 같습니다.
          * 결마다 빛이 드는 방향도 달리해야 같은 면이 아니라 따로 휘어 있는 띠로 보입니다.
          */}
        <linearGradient id={`${id}-back`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" style={{ stopColor: 'var(--rank-wave-a)' }} stopOpacity="0" />
          <stop offset="42%" style={{ stopColor: 'var(--rank-wave-a)' }} stopOpacity=".04" />
          <stop offset="76%" style={{ stopColor: 'var(--rank-wave-a)' }} stopOpacity=".13" />
          <stop offset="100%" style={{ stopColor: 'var(--rank-wave-b)' }} stopOpacity=".08" />
        </linearGradient>
        <linearGradient id={`${id}-mid`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" style={{ stopColor: 'var(--rank-wave-a)' }} stopOpacity="0" />
          <stop offset="38%" style={{ stopColor: 'var(--rank-wave-a)' }} stopOpacity=".06" />
          <stop offset="72%" style={{ stopColor: 'var(--rank-wave-a)' }} stopOpacity=".21" />
          <stop offset="100%" style={{ stopColor: 'var(--rank-wave-b)' }} stopOpacity=".14" />
        </linearGradient>
        <linearGradient id={`${id}-front`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" style={{ stopColor: 'var(--rank-wave-a)' }} stopOpacity="0" />
          <stop offset="44%" style={{ stopColor: 'var(--rank-wave-b)' }} stopOpacity=".07" />
          <stop offset="78%" style={{ stopColor: 'var(--rank-wave-b)' }} stopOpacity=".23" />
          <stop offset="100%" style={{ stopColor: 'var(--rank-wave-b)' }} stopOpacity=".12" />
        </linearGradient>
        {/*
          * 흐림은 띠 하나가 아니라 묶음 전체에 겁니다. 겹친 자리를 먼저 합친 다음 흐리기 때문에
          * 띠끼리 만나 생기는 경계선까지 같이 풀립니다. 띠마다 따로 걸면 그 경계가 그대로 남습니다.
          */}
        <filter id={`${id}-soft`} x="-45%" y="-45%" width="190%" height="190%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
      </defs>

      {/*
        * 따로 노는 띠 여럿이 아니라, 같은 길을 조금씩 내려 그린 결 넷입니다. 겹치는 자리가 흐름과
        * 나란해서 층이 아니라 한 줄기가 접힌 것으로 읽힙니다. 앞의 결일수록 조금 더 짙게 둡니다.
        */}
      <g filter={`url(#${id}-soft)`}>
        <path fill={`url(#${id}-back)`} d={waveRibbon(0, 40)} />
        <path fill={`url(#${id}-mid)`} d={waveRibbon(26, 34)} />
        <path fill={`url(#${id}-front)`} d={waveRibbon(52, 32)} />
        <path fill={`url(#${id}-mid)`} d={waveRibbon(76, 30)} />
      </g>
    </svg>
  );
}

/**
 * 1위 한 건을 크게 세우는 카드입니다. 순위 알약·키워드·분야만 위에 두고,
 * 줄을 세운 값 하나를 카드 바닥에 크게 깝니다. 여러 수치를 늘어놓는 대신 기준값 하나만 남깁니다.
 */
function RankHero({ trend, type, look }: { trend: Trend; type: TrendType; look: BoardLook }) {
  const openDetail = useTrendDetailLink();

  return (
    <article className="rank-hero">
      <HeroWave type={type} />
      {/* 담기 단추는 평소 숨어 있다가 카드에 손을 얹거나 초점이 가면 드러납니다. 담긴 것은 늘 보입니다. */}
      <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="rank-bookmark rank-bookmark--float" />

      {/* 두 자리로 맞춰야 01·02 처럼 폭이 고르게 읽힙니다. 낭독기에는 '1위'로 들리게 단위를 따로 답니다. */}
      <span className="rank-hero-rank">
        {String(trend.rank ?? 1).padStart(2, '0')}
        <span className="sr-only">위</span>
      </span>

      {/* 제목 링크가 카드 전체를 덮습니다(cover-link). 담기 단추는 덮개 위로 올라가 그대로 눌립니다. */}
      <h3><Link className="rank-hero-keyword cover-link" {...openDetail(trend.trendId)}>{trend.keyword}</Link></h3>
      <p className="rank-hero-label">{look.measure}</p>
      <p className="rank-hero-headline">{headline(trend, type)}</p>
    </article>
  );
}

function RankRow({ trend, type, rank }: { trend: Trend; type: TrendType; rank: number }) {
  const openDetail = useTrendDetailLink();

  return (
    <li className="rank-row">
      <span className="rank-row-rank">{rank}</span>
      <Link className="rank-row-keyword cover-link" {...openDetail(trend.trendId)}>{trend.keyword}</Link>
      <span className="rank-row-value">{headline(trend, type)}</span>
      <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="rank-bookmark" />
    </li>
  );
}

interface TrendRankBoardProps {
  type: TrendType;
  /** 분야 목록을 아직 못 받았으면 고를 분야가 없어 비어 있습니다. 그동안은 부르지 않습니다. */
  domain: string | undefined;
  period: PeriodCode;
  /** 검색어. 받아 온 판 안에서만 걸러 줍니다. */
  query: string;
}

/**
 * 한 갈래의 순위판입니다. 1위는 왼쪽 한 단을 통째로 쓰고, 2위부터는 오른쪽 단에 줄로 쌓입니다.
 *
 * 갈래마다 서버를 따로 불러야 해서 판이 제 조회를 들고 있습니다. '더보기'는 받는 개수를
 * 늘리는 것이라, 눌러도 1위 자리는 그대로 두고 오른쪽 줄만 길어집니다.
 */
export function TrendRankBoard({ type, domain, period, query }: TrendRankBoardProps) {
  const look = looks[type];
  const [size, setSize] = useState(TOP_COUNT);
  const listQuery = useTrends(domain ? { domain, type, period, page: 0, size } : undefined);

  const needle = query.trim().toLowerCase();
  const received = listQuery.data?.trends ?? [];
  const trends = needle ? received.filter((trend) => trend.keyword.toLowerCase().includes(needle)) : received;
  const [hero, ...rest] = trends;
  /* 검색어로 거른 판에서는 더 받아도 그 말이 든 트렌드가 나온다는 보장이 없어 내밀지 않습니다. */
  const canLoadMore = Boolean(hero) && !needle && (listQuery.data?.hasNext ?? false);

  return (
    <section className={`rank-board rank-board--${look.tone}`} aria-label={look.title}>
      <header className="rank-board-head">
        <span className="rank-board-icon"><BoardIcon path={look.icon} size={17} /></span>
        <div>
          <h2>{look.title}</h2>
          <p>{look.lead}</p>
        </div>
        {/* 화살표만 남긴 단추라 이름이 글자로 남지 않습니다. 읽어 줄 이름을 따로 답니다. */}
        {canLoadMore && (
          <button
            type="button"
            className="rank-board-more"
            title={`${look.title} 더보기`}
            aria-label={`${look.title} 더보기`}
            onClick={() => setSize((prev) => prev + TOP_COUNT)}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </button>
        )}
      </header>

      {listQuery.isLoading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}
      {!listQuery.isLoading && listQuery.isError && (
        <div className="trendin-state is-error" role="alert">
          <p>{look.title}을 불러오지 못했습니다.</p>
          <button type="button" onClick={() => void listQuery.refetch()}>다시 시도</button>
        </div>
      )}
      {!listQuery.isLoading && !listQuery.isError && !hero && (
        <div className="trendin-state" role="status">
          <p>{needle ? `‘${query}’와 맞는 트렌드가 없습니다.` : '아직 집계된 트렌드가 없습니다.'}</p>
        </div>
      )}

      {hero && (
        <div className="rank-board-body">
          <RankHero trend={hero} type={type} look={look} />
          <div className="rank-board-list">
            {/* 갈래마다 오른쪽 끝에 쓰는 값이 달라, 무엇으로 줄을 세웠는지 칸 이름으로 밝혀 둡니다. */}
            <div className="rank-list-head">
              <span>순위</span>
              <span>키워드</span>
              <span>{look.measure}</span>
            </div>
            <ol className="rank-board-rest">
              {rest.map((trend, index) => (
                <RankRow key={trend.trendId} trend={trend} type={type} rank={trend.rank ?? index + 2} />
              ))}
            </ol>
          </div>
        </div>
      )}
    </section>
  );
}
