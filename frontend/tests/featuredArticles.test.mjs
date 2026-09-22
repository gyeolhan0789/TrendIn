import assert from 'node:assert/strict';
import test from 'node:test';
import { FEATURED_ARTICLES } from '../src/features/trend/featuredArticles.ts';
import { FEATURED_CONTENT_GROUPS } from '../src/features/trend/featuredContentGroups.ts';

const expectedUrls = [
  'https://www.esquirekorea.co.kr/article/1909391',
  'https://www.marieclairekorea.com/fashion/2026/08/purple/',
  'https://www.elle.co.kr/article/1910038',
  'https://www.marieclairekorea.com/pinpage/2026/09/2026-fw-focus-trend/',
  'https://www.gqkorea.co.kr/2026/09/08/이번-주에-따라-입고-싶은-올가을-남자-스타일링-8/',
  'https://www.harpersbazaar.co.kr/article/1908247',
  'https://www.elle.com/fashion/shopping/a73393083/fall-2026-fashion-trends/',
  'https://www.allurekorea.com/2026/09/07/part-4-올-가을-기억해야-할-패션-키워드-11/',
  'https://www.marieclairekorea.com/fashion/2026/09/red/',
  'https://www.whowhatwear.com/fashion/fall/autumn-fashion-colour-combinations-2026',
  'https://www.vogue.com/article/fall-2026-color-trends',
  'https://www.harpersbazaar.com/fashion/trends/a73607408/fall-fashion-favorites-2026/',
];

test('고정 기사는 인기·신규·급상승 순서로 네 개씩 표시하며 URL이 겹치지 않는다', () => {
  const groups = FEATURED_CONTENT_GROUPS.map(({ type }) => FEATURED_ARTICLES[type]);
  assert.deepEqual(groups.map((articles) => articles.length), [4, 4, 4]);
  const articles = groups.flat();
  assert.deepEqual(articles.map(({ url }) => url), expectedUrls);
  assert.equal(new Set(articles.map(({ url }) => url)).size, 12);
  assert.ok(articles.every(({ title, description, keyword, source }) => title && description && keyword && source));
});
