import assert from 'node:assert/strict';
import test from 'node:test';
import {
  formatNotificationMessage,
  notificationTypeClass,
  notificationTypeLabels,
} from '../src/features/notification/notificationPresentation.ts';

test('네 가지 트렌드 알림과 레거시 알림의 표시 이름을 구분한다', () => {
  assert.deepEqual(notificationTypeLabels, {
    KEYWORD_SURGE: '상승',
    KEYWORD_DROP: '하락',
    NEW_TREND: '신규',
    TREND_TURNING_POINT: '주목',
    TREND_CHANGE: '트렌드',
  });
});

test('알림 유형을 스타일 클래스 이름으로 바꾼다', () => {
  assert.equal(notificationTypeClass('TREND_TURNING_POINT'), 'is-trend-turning-point');
});

test('API 메시지의 실제 키워드로 유형별 문구를 통일한다', () => {
  assert.equal(formatNotificationMessage({
    notificationType: 'KEYWORD_SURGE', message: "관심 키워드 '발레코어'가 급등했어요.",
  }), '“발레코어”가 빠르게 상승하고 있어요.');
  assert.equal(formatNotificationMessage({
    notificationType: 'NEW_TREND', message: "관심 키워드 '긱시크'가 신규 트렌드로 발견되었어요.",
  }), '“긱시크”가 새로운 트렌드로 떠올랐어요.');
  assert.equal(formatNotificationMessage({
    notificationType: 'KEYWORD_DROP', message: "관심 키워드 '카고 팬츠'가 트렌드에서 급락했어요.",
  }), '“카고 팬츠”가 트렌드에서 벗어났어요.');
});

test('전환점은 API 메시지에서 실제 변경 유형을 표시한다', () => {
  assert.equal(formatNotificationMessage({
    notificationType: 'TREND_TURNING_POINT',
    message: "관심 키워드 '레더 재킷'의 트렌드 유형이 신규에서 급상승으로 바뀌었어요.",
  }), '“레더 재킷”이 급상승 트렌드로 전환됐어요.');
});

test('키워드를 추출할 수 없는 레거시 메시지는 원문을 유지한다', () => {
  assert.equal(formatNotificationMessage({
    notificationType: 'TREND_CHANGE', message: '트렌드가 변경됐어요.',
  }), '트렌드가 변경됐어요.');
});
