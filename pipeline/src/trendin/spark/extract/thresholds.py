"""[04] 의 임계값과 도메인별 옵션 — `conf/*.yaml` 의 `extract` 구역.

**비어 있으면 Job 이 거부한다.** [03] 의 정제 문턱과 사정이 다르다 — 그쪽은 문턱이 없으면
아무 문서도 걸러지지 않고 전량 통과하는 것이 더 나빠 잠정값을 적었다. 여기는 값이 없으면
후보가 전부 살아남아 `pl_document_candidate` 가 잡음으로 차는데, 그걸 지우고 다시 돌리는
비용보다 시작을 거부하는 비용이 싸다 (`conf/base.yaml` 의 주석, [09 §7] 항목 5).

`base.yaml` 은 측정이 필요한 값을 `null` 로 두고, `local.yaml` 이 S6 측정을 돌릴 수 있게
잠정값을 채운다. S6 가 확정하면 `base.yaml` 로 옮기고 `pl_config_history` 에 초기값을 남긴다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.extract import morphology as mp

SECTION = "extract"

# 측정 없이 정할 수 없어 `base.yaml` 이 `null` 로 두는 키. 전부 있어야 시작한다.
REQUIRED = (
    "corpus_window_days",
    "df_min_ratio",
    "df_max_ratio",
    "score_weights.c_value",
    "score_weights.bm25",
    "score_weights.title",
    "per_document_top_k",
    "score_floor",
)


@dataclass(frozen=True, slots=True)
class ExtractThresholds:
    """[04] 의 숫자 전부. 한 곳에 모아 두는 이유는 S6 의 재확정이 파일 하나를 고치는 일이어야
    하기 때문이다."""

    # DF · BM25 의 말뭉치 = 같은 도메인의 최근 N 일 ([10 §2] 5번 — N 은 미확정).
    corpus_window_days: int
    # 구간에서 내는 n-gram 길이 상한. 4 이상은 거의 항상 문장 조각이다 ([04 §3]).
    ngram_max: int
    # 후보 문자 수 하한·상한 ([04 §5] 2번).
    min_chars: int
    max_chars: int
    # DF 하한·상한 — **절대값이 아니라 코퍼스 문서 수에 대한 비율** ([04 §5] 5·6번).
    df_min_ratio: float
    df_max_ratio: float
    # BM25 파라미터. 통상값에서 시작한다 ([04 §6]).
    bm25_k1: float
    bm25_b: float
    # 다섯 축의 가중합 ([04 §6] 결합). 뒤의 둘은 기본이 0 이라 켜야 돈다.
    weight_c_value: float
    weight_bm25: float
    weight_title: float
    # 선별 — 문서당 상위 K 이고 점수 하한 이상 ([04 §7]).
    per_document_top_k: int
    score_floor: float
    # 라틴 문자 표기 · 형태소 고유명사 ([04 §6] 고유명사 축, 2026-09-10 추가).
    # **`REQUIRED` 에 넣지 않는다** — 0 이면 옛 동작 그대로라, 비어 있는 것이 위험하지 않다.
    # `null` 로 거부해야 하는 값은 "없으면 잡음이 통과하는" 것들이다.
    weight_latin: float = 0.0
    weight_proper: float = 0.0

    @classmethod
    def from_config(cls, config: Config) -> "ExtractThresholds":
        section = config.section(SECTION)
        missing = [key for key in REQUIRED if _lookup(section, key) is None]
        if missing:
            raise ConfigError(
                "extract 임계값이 비어 있다 — 실데이터 분포를 재기 전이면 local.yaml 의 잠정값으로 "
                f"돌린다 ([09 §7] 항목 5): {', '.join(f'extract.{key}' for key in missing)}"
            )
        weights = section.get("score_weights") or {}
        bm25 = section.get("bm25") or {}
        candidate = section.get("candidate") or {}
        return cls(
            corpus_window_days=int(section["corpus_window_days"]),
            ngram_max=int(section.get("ngram_max", 3)),
            min_chars=int(candidate.get("min_chars", 2)),
            max_chars=int(candidate.get("max_chars", 40)),
            df_min_ratio=float(section["df_min_ratio"]),
            df_max_ratio=float(section["df_max_ratio"]),
            bm25_k1=float(bm25.get("k1", 1.2)),
            bm25_b=float(bm25.get("b", 0.75)),
            weight_c_value=float(weights["c_value"]),
            weight_bm25=float(weights["bm25"]),
            weight_title=float(weights["title"]),
            weight_latin=float(weights.get("latin") or 0.0),
            weight_proper=float(weights.get("proper") or 0.0),
            per_document_top_k=int(section["per_document_top_k"]),
            score_floor=float(section["score_floor"]),
        ).validated()

    def validated(self) -> "ExtractThresholds":
        if self.corpus_window_days < 0:
            raise ConfigError("extract.corpus_window_days 는 0 이상이어야 한다")
        if self.ngram_max < 1:
            raise ConfigError("extract.ngram_max 는 1 이상이어야 한다")
        if not 0 <= self.df_min_ratio <= self.df_max_ratio <= 1:
            raise ConfigError("extract.df_min_ratio ≤ df_max_ratio 이고 둘 다 0~1 이어야 한다")
        if self.per_document_top_k < 1:
            raise ConfigError("extract.per_document_top_k 는 1 이상이어야 한다")
        if self.weight_c_value + self.weight_bm25 + self.weight_title <= 0:
            raise ConfigError("extract.score_weights 의 합이 0 보다 커야 한다")
        return self


@dataclass(frozen=True, slots=True)
class DomainOptions:
    """[04 §8] — 같은 코드에 설정만 다르게. `extract.domains.{domain}` 에서 온다.

    | | 개발 | 패션 |
    | --- | --- | --- |
    | 코드 식별자 규칙 | 활성 | 비활성 (잡음만 는다) |
    | 해시태그 | 낮은 가중 | 높은 가중 |
    """

    # camelCase · snake_case · dotted 를 한 토큰으로 보존한다. 끄면 `.`·`_` 에서 쪼갠다.
    code_identifiers: bool = True
    # 해시태그 후보의 최종 점수에 곱한다. 1.0 이면 중립.
    hashtag_weight: float = 1.0
    # 형태소 분석기가 어절을 쪼갠 뒤 후보 표기를 어디까지 붙여 쓸지 (`morphology.SURFACE_*`).
    # 옛 `strip_single_josa` 가 있던 자리다 — 조사를 뗄지 말지가 아니라 **표기를 어디서 끊을지**
    # 가 남은 선택이다 ([04 §2]).
    surface_policy: str = mp.SURFACE_PREFIXED

    @classmethod
    def from_config(cls, config: Config, *, domain: str) -> "DomainOptions":
        section = config.section(f"{SECTION}.domains.{domain}")
        default = cls()
        policy = str(section.get("surface_policy", default.surface_policy))
        if policy not in mp.SURFACE_POLICIES:
            raise ConfigError(
                f"extract.domains.{domain}.surface_policy 는 "
                f"{' · '.join(mp.SURFACE_POLICIES)} 중 하나여야 한다: {policy!r}"
            )
        return cls(
            code_identifiers=bool(section.get("code_identifiers", default.code_identifiers)),
            hashtag_weight=float(section.get("hashtag_weight", default.hashtag_weight)),
            surface_policy=policy,
        )


def lexicon_dir(config: Config) -> str:
    """사전 디렉터리. `submit.sh` 가 `pipeline/` 에서 실행하므로 상대 경로가 거기 기준이다.

    불용어·노이즈 사전과 **형태소 분석기 사용자 사전**(`userdict-{domain}.txt`)이 같은
    디렉터리에 있다. 둘을 나누지 않은 이유는 셋 다 "손으로 고치는 목록" 이고 같은 주기로
    바뀌기 때문이다."""
    return str(config.get(f"{SECTION}.lexicon_dir", "spark/conf/lexicon"))


def _lookup(section: dict[str, Any], dotted: str) -> Any:
    node: Any = section
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node
