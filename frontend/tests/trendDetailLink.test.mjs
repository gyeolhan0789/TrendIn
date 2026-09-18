import assert from 'node:assert/strict';
import test from 'node:test';
import { URLSearchParams } from 'node:url';
import { trendDetailSearch, SAVED_TREND_PERIOD } from '../src/constants/filterCodes.ts';

for (const period of ['24H', '7D', '30D']) {
  test(`목록의 ${period} 선택을 상세로 전달한다`, () => {
    const query = new URLSearchParams(trendDetailSearch(`?period=${period}&page=3`));
    assert.equal(query.get('period'), period);
    assert.equal(query.has('page'), false);
  });
}

test('저장 목록의 상세는 이전 화면 기간과 무관하게 30D다', () => {
  const query = new URLSearchParams(trendDetailSearch('?period=24H', '?from=saved'));
  assert.equal(query.get('period'), SAVED_TREND_PERIOD);
  assert.equal(query.get('from'), 'saved');
});

test('명시한 상세 기간을 우선하고 잘못된 기간은 기본값으로 처리한다', () => {
  assert.equal(trendDetailSearch('?period=7D', '?period=30D'), '?period=30D');
  assert.equal(trendDetailSearch('?period=bad'), '?period=24H');
});
