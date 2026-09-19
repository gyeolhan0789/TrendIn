-- Widen the text columns on contents so long titles and URLs can be stored.
--
-- Content declares title, source and url with @Column(nullable = false) and no
-- length, so JPA's default of 255 became the column width. That default held
-- until articles started arriving that exceed it.
--
-- The cost is not the lost rows. The ingest job stages a whole batch and merges
-- it in one statement, so a single row over the limit rolls back the entire
-- merge: on 2026-09-19 six articles out of 27,791 stopped the pipeline for a
-- day, and the symptom surfaced as an empty trend page rather than as a write
-- error.
--
-- url cannot be truncated instead. It carries the unique constraint, and the
-- pipeline keys pl_content_id_map on the sha256 of the full string, so a
-- shortened url would collide with its neighbours and break that mapping.
--
-- 2048 leaves room above the longest values observed (274 for a title, 774 for
-- a newsletter tracking url) and stays far below the btree limit that
-- uk_contents_url depends on. Widening a varchar rewrites no table, and
-- Hibernate's ddl-auto: validate does not compare column lengths, so a running
-- backend is unaffected.

ALTER TABLE contents
    ALTER COLUMN title  TYPE varchar(2048),
    ALTER COLUMN url    TYPE varchar(2048),
    ALTER COLUMN source TYPE varchar(2048);
