-- Move the trend type badge from trends to keyword_metrics.
--
-- trends has no period column, so the three analysis periods (24H, 7D, 30D)
-- had to share one array and the pipeline stored their union. A keyword that
-- only qualifies as RISING over 30 days therefore showed up in the 7 day list
-- carrying that period's growth rate, which reads as a contradiction.
-- keyword_metrics is already unique per (keyword_id, period), so the judgement
-- belongs on that row.
--
-- The column type matches trends.trend_types rather than the trend_type domain
-- because the entity maps it with @JdbcTypeCode(SqlTypes.ARRAY), and the
-- baseline declared the existing array that way. The aggregate job inspects the
-- column type at run time and casts accordingly, so either declaration loads.
--
-- DEFAULT '{}' lets the NOT NULL apply to rows that already exist. The
-- aggregate job fills real values on its next run; until then every row reports
-- no trend types, which is what an unjudged row should say.

ALTER TABLE keyword_metrics
    ADD COLUMN trend_types varchar(255)[] NOT NULL DEFAULT '{}';
