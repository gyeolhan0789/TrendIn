"""[05] 시험이 함께 쓰는 문턱 생성자.

`conftest.py` 에 두고 `from conftest import ...` 로 가져오면 층 2 의
`tests/spark/conftest.py` 와 이름이 충돌한다 — 전체 수집에서 어느 쪽이 잡히는지가
디렉터리 순서에 달린다. 그래서 고유한 이름의 모듈로 둔다 (`tests/conftest.py` 가 이
디렉터리를 sys.path 에 넣는다).
"""

from __future__ import annotations

from trendin.spark.io.keywords import AliasResult
from trendin.spark.registry.thresholds import RegistryThresholds

# `spark/conf/local.yaml` 의 잠정값과 같은 숫자다. 시험이 설정 파일을 읽지 않는 이유는 그
# 값이 S6 에서 바뀔 예정이고, 바뀔 때 판정 시험이 함께 빨개지면 무엇이 깨진 것인지 알 수
# 없기 때문이다 — **판정과 설정을 따로 지킨다.**
DEFAULTS = dict(
    plural_df_dominance=5.0,
    abbreviation_min_documents=3,
    transliteration_floor=0.5,
    variant_min_length=5,
    variant_max_edit_distance=2,
    variant_df_dominance=10.0,
    variant_max_index_size=20000,
    alias_max_group_size=10,
    promote_min_documents=5,
    promote_min_observed_days=2,
    promote_min_authors=3,
    promote_min_representative_ratio=0.6,
    embedding_model=None,
    embedding_dim=8,
    embedding_batch_size=4,
    review_similarity_floor=None,
    review_npmi_ceiling=None,
)


def make_registry_thresholds(**overrides) -> RegistryThresholds:
    """문턱 하나만 바꿔 그 조건이 걸리는지 보는 시험용 생성자.

    **`validated()` 를 부르지 않는다** — 말이 안 되는 값을 만들어 검사가 잡는지 보는
    시험이 있어서다 (`test_registry_thresholds.py`).
    """
    return RegistryThresholds(**{**DEFAULTS, **overrides})


DOMAIN = "fashion"
DOMAIN_ENUM = "FASHION"
RUN_ID = "run-0001"

# 문턱을 딱 만족하는 관측. 한 칸씩 깎아 그 조건이 걸리는지 본다.
PASSING = dict(doc_count=5, observed_days=2, source_count=2, author_count=3)


def observation(key, *, surface=None, keyword_id=None, **counts):
    """`io/keywords.OBSERVATION_SQL` 한 행 — `(키, 표기, 상태, keyword_id, 넷)`."""
    values = {**PASSING, **counts}
    return (
        key,
        surface or key,
        "CANDIDATE",
        keyword_id,
        values["doc_count"],
        values["observed_days"],
        values["source_count"],
        values["author_count"],
    )


def group(key, **counts):
    """`GROUP_OBSERVATION_SQL` 한 행 — 별칭을 접은 뒤의 대표별 관측."""
    values = {**PASSING, **counts}
    return (
        key,
        values["doc_count"],
        values["observed_days"],
        values["source_count"],
        values["author_count"],
    )


class FakeRegistry:
    """`pl_` 표 대신 메모리. **부른 순서를 기억한다** — 그것이 정확성 조건이라서다."""

    def __init__(self, *, observations=(), groups=None, aliases=(), approved=(), decided=()):
        self._observations = tuple(observations)
        # 안 주면 관측을 그대로 쓴다 — 별칭이 없는 회차는 둘이 같다.
        self._groups = (
            tuple(groups)
            if groups is not None
            else tuple(
                group(
                    row[0],
                    doc_count=row[4],
                    observed_days=row[5],
                    source_count=row[6],
                    author_count=row[7],
                )
                for row in self._observations
            )
        )
        self._aliases = tuple(aliases)
        self._approved = tuple(approved)
        self._decided = tuple(decided)
        self.calls = []
        self.applied = []
        self.enqueued = []
        self.encoded_models = []

    def observations(self, *, domain):
        self.calls.append("observations")
        return self._observations

    def group_observations(self, *, domain):
        self.calls.append("group_observations")
        return self._groups

    def abbreviation_evidence(self, *, domain):
        return ()

    def aliases(self, *, domain):
        return self._aliases

    def approved_pairs(self, *, domain):
        return tuple((domain, rep, absorbed) for rep, absorbed in self._approved)

    def decided_pairs(self, *, domain):
        return tuple((domain, rep, absorbed, status) for rep, absorbed, status in self._decided)

    def apply_aliases(self, rows, *, domain):
        self.calls.append("apply_aliases")
        self.applied.extend(rows)
        return AliasResult(aliases=len(rows), new_or_changed=len(rows), recounted_dates=1)

    def enqueue_review(self, rows):
        self.enqueued.extend(rows)
        return len(rows)

    def cached_vectors(self, *, model):
        self.encoded_models.append(model)
        return {}

    def cache_vectors(self, rows):
        return len(rows)


class FakeKeywords:
    def __init__(self):
        self.promoted = []
        self.linked = 0

    def promote(self, rows):
        self.promoted.extend(rows)
        return len(rows)

    def stage_and_link_contents(self, *, domain, extract_run_id):
        self.linked = 2
        return self.linked


def value_of(result, metric, dimension=DOMAIN):
    """통계 한 칸. 같은 `(metric, dimension)` 이 두 번 남으면 거기서 죽는다 — `io/stats.py`
    의 PK 가 그 조합이라 DB 에서는 뒤엣것이 이기고, 시험에서는 조용히 앞엣것을 본다."""
    values = [
        stat.value for stat in result.stats if stat.metric == metric and stat.dimension == dimension
    ]
    assert len(values) <= 1, f"{metric}/{dimension} 이 두 번 남았다"
    return values[0] if values else None
