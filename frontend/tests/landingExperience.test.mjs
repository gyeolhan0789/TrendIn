import assert from 'node:assert/strict';
import test from 'node:test';
import {
  claimFirstLandingAnimation,
  claimFirstLandingGuide,
  resetLandingGuide,
} from '../src/utils/landingExperience.ts';

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test('파도 등장 애니메이션은 같은 브라우저 세션에서 한 번만 최초로 판정한다', () => {
  const storage = memoryStorage();

  assert.equal(claimFirstLandingAnimation(storage), true);
  assert.equal(claimFirstLandingAnimation(storage), false);
});

test('조작 안내는 같은 로그인 세션에서 한 번만 최초로 판정한다', () => {
  const storage = memoryStorage();

  assert.equal(claimFirstLandingGuide(storage), true);
  assert.equal(claimFirstLandingGuide(storage), false);
  resetLandingGuide(storage);
  assert.equal(claimFirstLandingGuide(storage), true);
});
