import assert from 'node:assert/strict';
import test from 'node:test';
import { FEATURED_CONTENT_GROUPS } from '../src/features/trend/featuredContentGroups.ts';

test('홈 대표 콘텐츠는 인기, 신규, 급상승 순서로 전환한다', () => {
  assert.deepEqual(
    FEATURED_CONTENT_GROUPS.map(({ type, label }) => [type, label]),
    [
      ['CURRENT', '인기'],
      ['NEW', '신규'],
      ['RISING', '급상승'],
    ],
  );
});
