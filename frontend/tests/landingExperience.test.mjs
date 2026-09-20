import assert from 'node:assert/strict';
import test from 'node:test';
import { claimFirstLandingExperience } from '../src/pages/LandingPage/landingExperience.ts';

test('랜딩 경험은 같은 세션에서 한 번만 최초로 판정한다', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };

  assert.equal(claimFirstLandingExperience(storage), true);
  assert.equal(claimFirstLandingExperience(storage), false);
});
