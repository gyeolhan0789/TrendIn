"""`concept.*` 설정.

측정으로 정할 값이 아니라 **정책** 값이라 `base.yaml` 에 숫자가 있다. `ingest.normalize` 와
같은 사정이다 — 비워 두면 Job 이 거부하는 것이 아니라 아무것도 안 걸러지고 조용히 통과한다.
그래도 `null` 로 지운 것은 받지 않는다: 값이 없으면 "정하지 않았다" 이고, 정하지 않은 채
돌리는 것보다 시작을 거부하는 것이 싸다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

from dataclasses import dataclass

from trendin.spark.common.config import Config, ConfigError

SECTION = "concept"

REQUIRED = (
    "window_days",
    "unmapped.min_articles",
    "unmapped.context_samples",
)


@dataclass(frozen=True, slots=True)
class ConceptThresholds:
    # 최근 며칠 분의 선별 후보를 다시 붙이나. `aggregate.recompute_window_days` 와 같은 뜻이다 —
    # 사전이 바뀌면 이 창 안의 기사는 다음 실행이 저절로 고친다. 밖의 기사는 손으로 다시 돌린다.
    window_days: int
    # 미등록 표현이 후보 생성·판정 대상이 되는 기사 수. 승격 관문과 같은 눈금이다.
    min_articles: int
    # 표현당 남기는 문맥 표본 수. 검수자가 읽을 양이고 판정에 넣을 양이다.
    context_samples: int
    # 초기 사전 파일이 있는 곳. 저장소 루트 기준.
    seed_dir: str

    @classmethod
    def from_config(cls, config: Config) -> "ConceptThresholds":
        section = config.section(SECTION)
        missing = [key for key in REQUIRED if _lookup(section, key) is None]
        if missing:
            raise ConfigError(
                "concept 설정이 비어 있다 — base.yaml 의 값을 지웠으면 되돌린다: "
                + ", ".join(f"concept.{key}" for key in missing)
            )
        unmapped = section.get("unmapped") or {}
        return cls(
            window_days=int(section["window_days"]),
            min_articles=int(unmapped["min_articles"]),
            context_samples=int(unmapped["context_samples"]),
            seed_dir=str(section.get("seed_dir") or "spark/conf/concepts"),
        ).validated()

    def validated(self) -> "ConceptThresholds":
        if self.window_days < 1:
            raise ConfigError("concept.window_days 는 1 이상이어야 한다")
        if self.min_articles < 1:
            raise ConfigError("concept.unmapped.min_articles 는 1 이상이어야 한다")
        if self.context_samples < 1:
            raise ConfigError("concept.unmapped.context_samples 는 1 이상이어야 한다")
        return self


def _lookup(section: dict, dotted: str):
    node = section
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node
