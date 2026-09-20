import assert from 'node:assert/strict';
import test from 'node:test';
import { filterDetailKeywords, isDetailKeyword } from '../src/features/trend/detailKeyword.ts';

const keyword = (keywordId, trendId) => ({
  keywordId,
  keyword: `키워드 ${keywordId}`,
  domain: { domain: 'FASHION', name: '패션' },
  trendId,
  trendTypes: [],
  growthRate: null,
});

test('유효한 트렌드 상세 ID가 있는 검색 결과만 남긴다', () => {
  const result = filterDetailKeywords([
    keyword(1, null),
    keyword(2, 0),
    keyword(3, -1),
    keyword(4, 101),
  ]);

  assert.deepEqual(result.map((item) => item.keywordId), [4]);
  assert.equal(result[0].trendId, 101);
});

test('검색 결과별 상세 이동 가능 여부를 구분한다', () => {
  assert.equal(isDetailKeyword(keyword(1, null)), false);
  assert.equal(isDetailKeyword(keyword(2, 0)), false);
  assert.equal(isDetailKeyword(keyword(3, 101)), true);
});
