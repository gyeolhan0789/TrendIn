import assert from 'node:assert/strict';
import test from 'node:test';
import { conceptGloss, countryTrendLabel } from '../src/features/globalTrend/conceptGloss.ts';

test('원문과 다른 개념 이름은 그대로 덧붙인다', () => {
  assert.equal(conceptGloss('pelle', 'leather'), 'leather');
  assert.equal(conceptGloss('가죽', 'leather'), 'leather');
});

test('대소문자만 다른 같은 말은 덧붙이지 않는다', () => {
  assert.equal(conceptGloss('Leather', 'leather'), null);
  assert.equal(conceptGloss(' cargo pants ', 'Cargo Pants'), null);
});

test('개념 이름이 없으면 덧붙이지 않는다', () => {
  assert.equal(conceptGloss('낯선 말', null), null);
  assert.equal(conceptGloss('낯선 말', undefined), null);
  assert.equal(conceptGloss('낯선 말', '  '), null);
});

test('국가별 트렌드는 한국만 원문을 유지하고 해외는 개념 이름을 우선한다', () => {
  assert.equal(countryTrendLabel('KR', '뉴발란스', 'New Balance'), '뉴발란스');
  assert.equal(countryTrendLabel('JP', 'ニューバランス', 'New Balance'), 'New Balance');
  assert.equal(countryTrendLabel('IT', 'pelle', 'leather'), 'leather');
  assert.equal(countryTrendLabel('JP', '未登録', null), '未登録');
});
