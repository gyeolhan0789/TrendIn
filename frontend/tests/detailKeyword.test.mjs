import assert from 'node:assert/strict';
import test from 'node:test';
import { filterDetailKeywords } from '../src/features/trend/detailKeyword.ts';

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
