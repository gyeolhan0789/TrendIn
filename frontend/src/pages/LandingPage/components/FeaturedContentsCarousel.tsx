import { useState } from 'react';
import { CylinderCarousel } from '../../../components/common/CylinderCarousel';
import { FEATURED_CONTENT_GROUPS } from '../../../features/trend/featuredContentGroups';
import { useFeaturedTrendContents } from '../../../features/trend/hooks/useFeaturedTrendContents';
import type { TrendType } from '../../../features/trend/types/trend';

interface FeaturedContentsCarouselProps {
  domain: string | undefined;
  noChosenDomain: boolean;
}

/** 트렌드 탐색과 같은 순서와 조작법으로 대표 콘텐츠 세 갈래를 넘겨 봅니다. */
export function FeaturedContentsCarousel({ domain, noChosenDomain }: FeaturedContentsCarouselProps) {
  const [index, setIndex] = useState(0);
  const slides = FEATURED_CONTENT_GROUPS.map((group) => ({
    key: group.type,
    label: group.label,
    node: (
      <FeaturedContentsSlide
        domain={domain}
        type={group.type}
        label={group.label}
        noChosenDomain={noChosenDomain}
      />
    ),
  }));

  return (
    <div className="featured-carousel">
      <CylinderCarousel
        slides={slides}
        index={index}
        onIndexChange={setIndex}
        ariaLabel="주목할 만한 콘텐츠 갈래"
      />
    </div>
  );
}

interface FeaturedContentsSlideProps extends FeaturedContentsCarouselProps {
  type: TrendType;
  label: string;
}

function FeaturedContentsSlide({ domain, type, label, noChosenDomain }: FeaturedContentsSlideProps) {
  const query = useFeaturedTrendContents(domain, type);

  return (
    <div aria-label={`${label} 트렌드 대표 콘텐츠`}>
      <div className="featured-grid">
        {query.data?.map(({ trend, content }, index) => (
          <a className="featured-card" href={content.url} key={trend.trendId} target="_blank" rel="noreferrer">
            {/* 받은 차례입니다. `trend.rank` 는 분야 전체의 언급량 순위라 갈래 판의 번호로 쓰면 뒤섞입니다. */}
            <span className="featured-tag">{label} {index + 1}위 · {trend.keyword}</span>
            <div>
              <h3>{content.title}</h3>
              <p>{trend.description ?? `${trend.keyword} 트렌드의 대표 콘텐츠입니다.`}</p>
            </div>
            <span className="featured-meta">{content.source} · {formatPublishedAt(content.publishedAt)}</span>
          </a>
        ))}
      </div>
      {noChosenDomain && <p className="featured-state">고른 관심 분야가 없어 보여 줄 콘텐츠가 없습니다.</p>}
      {!noChosenDomain && query.isPending && <p className="featured-state">콘텐츠를 불러오는 중입니다.</p>}
      {query.isError && (
        <div className="featured-state" role="alert">
          콘텐츠를 불러오지 못했습니다. <button type="button" onClick={() => void query.refetch()}>다시 시도</button>
        </div>
      )}
      {!query.isPending && !query.isError && query.data?.length === 0 && (
        <p className="featured-state">아직 소개할 콘텐츠가 없습니다.</p>
      )}
    </div>
  );
}

function formatPublishedAt(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('ko-KR', { month: 'short', day: 'numeric' }).format(date);
}
