import type { TrendType } from './types/trend';

export interface FeaturedArticle {
  title: string;
  titleLines?: readonly [string, string];
  description: string;
  keyword: string;
  source: string;
  url: string;
}

/** 홈에 고정 노출할 큐레이션 기사. 각 그룹은 입력 순서대로 네 개씩 보여 준다. */
export const FEATURED_ARTICLES: Record<TrendType, readonly FeaturedArticle[]> = {
  CURRENT: [
    { title: "느좋 가을 남자를 위한 '체크 셔츠' 7", titleLines: ['느좋 가을 남자를 위한', "'체크 셔츠' 7"], description: '가을에 입기 좋은 체크 셔츠와 스타일링 방법을 살펴봅니다.', keyword: '체크 셔츠', source: 'Esquire Korea', url: 'https://www.esquirekorea.co.kr/article/1909391' },
    { title: '올가을, 퍼플 컬러를 기억하세요', description: '가을·겨울 룩에 존재감을 더하는 퍼플 컬러를 소개합니다.', keyword: '퍼플 컬러', source: 'Marie Claire Korea', url: 'https://www.marieclairekorea.com/fashion/2026/08/purple/' },
    { title: '요즘 뉴요커들은 죄다 이렇게 입더라고요', description: '뉴욕 거리에서 눈에 띄는 가을 스타일링을 모았습니다.', keyword: '뉴욕 스트리트', source: 'ELLE Korea', url: 'https://www.elle.co.kr/article/1910038' },
    { title: '미리보는 2026 FW 가장 주목할 트렌드', description: '이번 가을·겨울 컬렉션에서 주목할 패션 흐름을 살펴봅니다.', keyword: '2026 FW', source: 'Marie Claire Korea', url: 'https://www.marieclairekorea.com/pinpage/2026/09/2026-fw-focus-trend/' },
  ],
  NEW: [
    { title: '이번 주에 따라 입고 싶은, 올가을 남자 스타일링 8', description: '이번 가을 참고하기 좋은 남성 스타일링을 소개합니다.', keyword: '남자 스타일링', source: 'GQ Korea', url: 'https://www.gqkorea.co.kr/2026/09/08/이번-주에-따라-입고-싶은-올가을-남자-스타일링-8/' },
    { title: '올가을엔 이 컬러 조합을 주목하세요!', description: '레드와 핑크처럼 눈길을 끄는 가을 컬러 조합을 살펴봅니다.', keyword: '컬러 조합', source: "Harper's Bazaar Korea", url: 'https://www.harpersbazaar.co.kr/article/1908247' },
    { title: '6 Fall 2026 Fashion Trends to Shop Right Now', description: '2026년 가을에 주목할 여섯 가지 패션 트렌드를 소개합니다.', keyword: '가을 패션 트렌드', source: 'ELLE', url: 'https://www.elle.com/fashion/shopping/a73393083/fall-2026-fashion-trends/' },
    { title: '올가을 기억해야 할 패션 키워드 11', description: '이번 시즌 눈여겨볼 패션 키워드를 한눈에 살펴봅니다.', keyword: '패션 키워드', source: 'Allure Korea', url: 'https://www.allurekorea.com/2026/09/07/part-4-올-가을-기억해야-할-패션-키워드-11/' },
  ],
  RISING: [
    { title: '제니부터 해리 스타일스까지, 지금 레드를 즐기는 방법', description: '일상에 레드 컬러를 자연스럽게 더하는 방법을 소개합니다.', keyword: '레드 스타일링', source: 'Marie Claire Korea', url: 'https://www.marieclairekorea.com/fashion/2026/09/red/' },
    { title: '6 Colour Combinations Cool Girls Are Wearing for Autumn 2026', description: '올가을 스타일링에 활용할 만한 컬러 조합을 모았습니다.', keyword: '가을 컬러 조합', source: 'Who What Wear', url: 'https://www.whowhatwear.com/fashion/fall/autumn-fashion-colour-combinations-2026' },
    { title: 'The Top Fall 2026 Color Trends, From Royal Purple to Juicy Peach', description: '런웨이에서 포착한 2026년 가을의 주요 색상을 살펴봅니다.', keyword: '가을 컬러 트렌드', source: 'Vogue', url: 'https://www.vogue.com/article/fall-2026-color-trends' },
    { title: 'The Best Fall Fashion Buys for Women in 2026, According to Experts', description: '가을 옷장을 준비할 때 참고할 만한 패션 아이템을 소개합니다.', keyword: '가을 패션 아이템', source: "Harper's Bazaar", url: 'https://www.harpersbazaar.com/fashion/trends/a73607408/fall-fashion-favorites-2026/' },
  ],
};
