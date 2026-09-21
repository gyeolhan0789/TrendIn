import assert from 'node:assert/strict';
import test from 'node:test';
import {
  getNextNotificationPage,
  MAX_NOTIFICATION_COUNT,
  NOTIFICATION_PAGE_SIZE,
} from '../src/features/notification/notificationPagination.ts';

test('알림을 다섯 개씩 최대 열다섯 개까지 불러온다', () => {
  assert.equal(NOTIFICATION_PAGE_SIZE, 5);
  assert.equal(MAX_NOTIFICATION_COUNT, 15);
  assert.equal(getNextNotificationPage({ page: 0, hasNext: true }), 1);
  assert.equal(getNextNotificationPage({ page: 1, hasNext: true }), 2);
  assert.equal(getNextNotificationPage({ page: 2, hasNext: true }), undefined);
});

test('다음 알림이 없으면 더 불러오지 않는다', () => {
  assert.equal(getNextNotificationPage({ page: 0, hasNext: false }), undefined);
});
