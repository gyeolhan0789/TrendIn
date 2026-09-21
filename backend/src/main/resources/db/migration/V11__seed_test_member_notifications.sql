-- dev의 UI 확인 계정에 네 가지 유형의 미읽음 알림을 한 번씩 추가한다.
-- 계정이나 연결할 트렌드가 없으면 아무 행도 만들지 않으며, dedup_key로 재실행 중복을 막는다.
WITH target_member AS (
    SELECT id
    FROM members
    WHERE email = 'test@test.com'
),
ranked_trends AS (
    SELECT trend.id,
           keyword.name,
           row_number() OVER (ORDER BY trend.id) AS slot
    FROM trends trend
    JOIN keywords keyword ON keyword.id = trend.keyword_id
    ORDER BY trend.id
    LIMIT 4
),
notification_specs(slot, notification_type, message_template, minute_offset) AS (
    VALUES
        (1, 'KEYWORD_SURGE', '%s가 빠르게 상승하고 있어요.', 0),
        (2, 'NEW_TREND', '%s가 새로운 트렌드로 떠올랐어요.', 1),
        (3, 'TREND_TURNING_POINT', '%s의 트렌드 유형이 신규에서 급상승으로 바뀌었어요.', 2),
        (4, 'KEYWORD_DROP', '%s가 트렌드에서 벗어났어요.', 3)
)
INSERT INTO notifications (
    member_id,
    trend_id,
    notification_type,
    message,
    is_read,
    created_at,
    dedup_key
)
SELECT target_member.id,
       ranked_trends.id,
       notification_specs.notification_type,
       format(notification_specs.message_template, quote_literal(ranked_trends.name)),
       false,
       CURRENT_TIMESTAMP - notification_specs.minute_offset * INTERVAL '1 minute',
       'seed:test@test.com:trend-notification:' || notification_specs.notification_type
FROM target_member
JOIN notification_specs ON true
JOIN ranked_trends ON ranked_trends.slot = notification_specs.slot
ON CONFLICT (dedup_key) DO NOTHING;
