-- Enforce one row per keyword and period in the metric tables.
--
-- The entity-declared constraints are wider: keyword_metrics is unique on four
-- columns (keyword_id, period, period_start, period_end) and
-- keyword_metric_history on three (keyword_id, bucket_start, bucket_end).
-- Because the window boundaries are part of the key, a batch that rolls over to
-- the next day inserts a second row for the same keyword and period instead of
-- updating the existing one.
--
-- The Spark aggregate job already deletes the stale rows, but only for the rows
-- it wrote itself. These indexes let the database reject duplicates from any
-- path. Adding an index does not change a column type, so Hibernate's
-- ddl-auto: validate is unaffected.

CREATE UNIQUE INDEX uk_keyword_metrics_keyword_period
    ON keyword_metrics (keyword_id, period);

CREATE UNIQUE INDEX uk_keyword_metric_history_keyword_bucket
    ON keyword_metric_history (keyword_id, bucket_start);
