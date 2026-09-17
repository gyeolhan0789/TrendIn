"""분석 당시의 유형과 AI 결과를 trend_analyses에 기간별로 저장한다."""

from __future__ import annotations

from typing import TYPE_CHECKING

from trendin.ai.analyzer import TrendAnalysis
from trendin.ai.articles import TrendTarget

if TYPE_CHECKING:
    from trendin.spark.common.config import Config


UPSERT_ANALYSIS_SQL = """
INSERT INTO trend_analyses (
    trend_id, period, trend_types, description, summary, reason,
    input_fingerprint, analyzed_at
)
SELECT t.id, %s::metric_period, %s::varchar(255)[], %s, %s, %s, %s, now()
  FROM trends t
 WHERE t.keyword_id = %s
ON CONFLICT (trend_id, period) DO UPDATE SET
    trend_types = EXCLUDED.trend_types,
    description = EXCLUDED.description,
    summary = EXCLUDED.summary,
    reason = EXCLUDED.reason,
    input_fingerprint = EXCLUDED.input_fingerprint,
    analyzed_at = EXCLUDED.analyzed_at
RETURNING trend_id
"""

CURRENT_ANALYSIS_SQL = """
SELECT EXISTS (
    SELECT 1
      FROM trend_analyses a
      JOIN trends t ON t.id = a.trend_id
     WHERE t.keyword_id = %s
       AND a.period = %s::metric_period
       AND a.input_fingerprint = %s
)
"""


class TrendAnalysisStore:
    """성공한 분석만 (trend_id, period)에 upsert한다."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def is_current(self, target: TrendTarget, fingerprint: str) -> bool:
        from trendin.spark.io import jdbc

        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(CURRENT_ANALYSIS_SQL, (target.keyword_id, target.period, fingerprint))
            return bool(cur.fetchone()[0])

    def save(self, target: TrendTarget, analysis: TrendAnalysis, fingerprint: str) -> int:
        from trendin.spark.io import jdbc

        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                UPSERT_ANALYSIS_SQL,
                (
                    target.period,
                    list(target.trend_types),
                    analysis.description,
                    analysis.summary,
                    analysis.reason,
                    fingerprint,
                    target.keyword_id,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("분석 대상 trends 행이 없어 기간별 분석을 저장하지 못했다")
        return int(row[0])
