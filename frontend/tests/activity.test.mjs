import assert from 'node:assert/strict';
import test from 'node:test';
import { buildActivities, formatActivityDate, groupByDate } from '../src/features/myPage/activity.ts';

const notification = (id, createdAt, message = '메시지') => ({
  notificationId: id,
  trendId: id * 10,
  notificationType: 'TREND_CHANGE',
  message,
  isRead: false,
  createdAt,
});

const saved = (id, savedAt, keyword = '키워드') => ({
  savedTrendId: id,
  trendId: id * 100,
  keywordId: id,
  keyword,
  domain: { domain: 'DEVELOP', name: '개발' },
  trendTypes: ['RISING'],
  description: null,
  mentionCount: null,
  growthRate: null,
  savedAt,
});

test('알림과 담은 트렌드를 최근 것부터 한 줄기로 세운다', () => {
  const rows = buildActivities(
    [notification(1, '2026-09-17T09:00:00+09:00'), notification(2, '2026-09-15T11:20:00+09:00')],
    [saved(3, '2026-09-16T18:45:00+09:00')],
  );

  assert.deepEqual(rows.map((row) => row.id), ['noti-1', 'saved-3', 'noti-2']);
  assert.deepEqual(rows.map((row) => row.kind), ['surge', 'saved', 'surge']);
});

test('서버가 보낸 시각을 기기 시간대로 바꾸지 않고 그대로 자른다', () => {
  const [row] = buildActivities([notification(1, '2026-09-17T23:40:00+09:00')], []);
  assert.equal(row.date, '2026-09-17');
  assert.equal(row.time, '23:40');
});

test('읽을 수 없는 시각은 줄을 세울 수 없어 빼고 지나간다', () => {
  assert.deepEqual(buildActivities([notification(1, '')], [saved(2, 'nope')]), []);
});

test('담은 트렌드 줄은 키워드를 문장에 넣어 보여 준다', () => {
  const [row] = buildActivities([], [saved(1, '2026-09-17T10:00:00+09:00', 'MCP 서버 구축')]);
  assert.equal(row.text, '"MCP 서버 구축" 트렌드를 저장했습니다');
});

test('같은 날짜끼리 묶고 받은 순서는 그대로 둔다', () => {
  const groups = groupByDate(buildActivities(
    [notification(1, '2026-09-17T09:00:00+09:00'), notification(2, '2026-09-17T08:00:00+09:00')],
    [saved(3, '2026-09-16T18:45:00+09:00')],
  ));

  assert.deepEqual(groups.map((group) => group.date), ['2026-09-17', '2026-09-16']);
  assert.deepEqual(groups[0].items.map((item) => item.time), ['09:00', '08:00']);
});

test('요 이틀만 말로 부르고 그 앞은 날짜로 적는다', () => {
  const day = (offset) => {
    const date = new Date();
    date.setDate(date.getDate() + offset);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  };

  assert.equal(formatActivityDate(day(0)), '오늘');
  assert.equal(formatActivityDate(day(-1)), '어제');
  assert.equal(formatActivityDate('2026-09-05'), '9월 5일');
});

test('알림 줄은 읽음 여부와 읽음 처리에 쓸 식별자를 함께 나른다', () => {
  const read = { ...notification(1, '2026-09-17T09:00:00+09:00'), isRead: true };
  const rows = buildActivities([notification(2, '2026-09-17T10:00:00+09:00'), read], []);

  assert.deepEqual(rows.map((row) => row.unread), [true, false]);
  assert.deepEqual(rows.map((row) => row.notificationId), [2, 1]);
});

test('담은 트렌드 줄은 읽고 말고가 없어 늘 읽은 것으로 둔다', () => {
  const [row] = buildActivities([], [saved(1, '2026-09-17T10:00:00+09:00')]);
  assert.equal(row.unread, false);
  assert.equal(row.notificationId, undefined);
});
