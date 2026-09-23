CREATE DOMAIN IF NOT EXISTS metric_period AS VARCHAR(3);
CREATE DOMAIN IF NOT EXISTS trend_type AS VARCHAR(20);

-- Concept tables are created and filled by the pipeline (pipeline/src/trendin/spark/io/concepts.py),
-- not by Flyway. The backend only reads them, so only the columns it reads are mirrored here.
CREATE TABLE IF NOT EXISTS pl_concept (
    id             BIGINT       PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE'
);
CREATE TABLE IF NOT EXISTS pl_concept_expression (
    id         BIGINT       PRIMARY KEY,
    concept_id BIGINT       NOT NULL REFERENCES pl_concept (id),
    lang       VARCHAR(10)  NOT NULL,
    normalized VARCHAR(255) NOT NULL,
    status     VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE'
);
