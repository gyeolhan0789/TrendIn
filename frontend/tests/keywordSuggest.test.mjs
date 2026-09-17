import assert from 'node:assert/strict';
import test from 'node:test';
import { nextSuggestIndex, splitMatch } from '../src/features/trend/keywordSuggest.ts';

test('위아래 키는 아무 줄도 고르지 않은 자리에서 양 끝으로 들어간다', () => {
  assert.equal(nextSuggestIndex(-1, 3, true), 0);
  assert.equal(nextSuggestIndex(-1, 3, false), 2);
});

test('위아래 키는 끝에 닿으면 반대쪽 끝으로 돈다', () => {
  assert.equal(nextSuggestIndex(2, 3, true), 0);
  assert.equal(nextSuggestIndex(0, 3, false), 2);
  assert.equal(nextSuggestIndex(0, 3, true), 1);
});

test('고를 줄이 없으면 고르지 않은 자리에 머문다', () => {
  assert.equal(nextSuggestIndex(-1, 0, true), -1);
  assert.equal(nextSuggestIndex(1, 0, false), -1);
});

test('검색어와 겹치는 자리를 대소문자와 상관없이 가려낸다', () => {
  assert.deepEqual(splitMatch('Generative AI', 'ai'), ['Generative ', 'AI', '']);
  assert.deepEqual(splitMatch('생성형 AI', '생성'), ['', '생성', '형 AI']);
});

test('겹치는 자리가 없거나 검색어가 비면 통째로 둔다', () => {
  assert.deepEqual(splitMatch('생성형 AI', '반도체'), ['생성형 AI', '', '']);
  assert.deepEqual(splitMatch('생성형 AI', ''), ['생성형 AI', '', '']);
});
