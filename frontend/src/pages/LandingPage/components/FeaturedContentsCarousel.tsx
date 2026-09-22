import { useState } from 'react';
import { CylinderCarousel } from '../../../components/common/CylinderCarousel';
import { FEATURED_ARTICLES } from '../../../features/trend/featuredArticles';
import { FEATURED_CONTENT_GROUPS } from '../../../features/trend/featuredContentGroups';

/** 트렌드 탐색과 같은 조작법으로 고정 큐레이션 기사 세 갈래를 넘겨 봅니다. */
export function FeaturedContentsCarousel() {
  const [index, setIndex] = useState(0);
  const slides = FEATURED_CONTENT_GROUPS.map((group) => ({
    key: group.type,
    label: group.label,
    node: <div className="featured-grid" aria-label={`${group.label} 추천 콘텐츠`}>
      {FEATURED_ARTICLES[group.type].map((article) => (
        <a className="featured-card" href={article.url} key={article.url} target="_blank" rel="noreferrer">
          <span className="featured-tag">{article.keyword}</span>
          <div>
            <h3>{article.titleLines ? <>{article.titleLines[0]}<br />{article.titleLines[1]}</> : article.title}</h3>
            <p>{article.description}</p>
          </div>
          <span className="featured-meta">{article.source}</span>
        </a>
      ))}
    </div>,
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
