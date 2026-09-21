import assert from 'node:assert/strict';
import test from 'node:test';
import { developmentNotificationSamples } from '../src/features/notification/notificationSamples.ts';

test('개발용 알림 샘플은 네 가지 트렌드 유형을 모두 보여 준다', () => {
  assert.deepEqual(
    new Set(developmentNotificationSamples.map(({ notificationType }) => notificationType)),
    new Set(['KEYWORD_SURGE', 'KEYWORD_DROP', 'NEW_TREND', 'TREND_TURNING_POINT']),
  );
});

test('개발용 알림은 서버 식별자와 겹치지 않는 음수 식별자를 쓴다', () => {
  assert.equal(developmentNotificationSamples.every(({ notificationId }) => notificationId < 0), true);
});

test('개발용 목록도 최대 열다섯 개 펼침을 확인할 수 있다', () => {
  assert.equal(developmentNotificationSamples.length, 15);
});
