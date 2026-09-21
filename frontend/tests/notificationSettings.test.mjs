import assert from 'node:assert/strict';
import test from 'node:test';
import {
  defaultNotificationSettings,
  updateNotificationSetting,
} from '../src/features/notification/types/notificationSettings.ts';

test('한 알림 설정만 바꾸고 나머지 서버 설정을 보존한다', () => {
  const settings = {
    keywordSurgeEnabled: true,
    keywordDropEnabled: true,
    newTrendEnabled: true,
    trendTurningPointEnabled: true,
  };

  const updated = updateNotificationSetting(settings, 'keywordDropEnabled', false);

  assert.deepEqual(updated, { ...settings, keywordDropEnabled: false });
  assert.equal(settings.keywordDropEnabled, true);
});

test('설정 조회가 실패해도 네 가지 알림은 켜진 기본값으로 표시한다', () => {
  assert.deepEqual(defaultNotificationSettings, {
    keywordSurgeEnabled: true,
    keywordDropEnabled: true,
    newTrendEnabled: true,
    trendTurningPointEnabled: true,
  });
});
