"""[04] 의 임계값과 도메인별 옵션 — `conf/*.yaml` 의 `extract` 구역.

**측정 없이 정할 수 없는 값이 여덟에서 둘로 줄었다** (2026-09-16). 실체 인식으로 옮기면서
DF 상하한 · 다섯 축 가중치 · 코퍼스 창이 없어졌기 때문이다 (설정 잎으로는 23 → 15). 남은
둘은 아래 `REQUIRED` 이고, 그 밖에 손으로 고를 것은 라벨 목록과 모델 문턱뿐이다.

**아직 비어 있으면 Job 이 거부하는 값이 둘 있다** — `per_document_top_k` 와 `score_floor`.
근거가 없어서가 아니라 **실데이터에서 다시 재야 하는 값**이기 때문이다. 200건 표본에서는
상위 20 · 하한 0.15 가 가장 좋았지만(`scratchpad/kwlab/RESULTS.md` §1), 그 표본은 한국
매체 한국어뿐이다. `local.yaml` · `dev.yaml` 이 잠정값을 채우고, 실데이터 분포를 본 뒤
`base.yaml` 로 옮기며 `pl_config_history` 에 초기값을 남긴다 ([09 §7] 항목 5).

모델 이름 · 문턱 · 라벨은 반대로 **측정 근거가 있어 기본값을 둔다.** 문턱 0.15 는 0.35 보다
F1 이 높았고(0.470 대 0.461), 라벨에서 색상을 뺀 것은 0.470 → 0.504 였다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.extract import adapters
from trendin.spark.extract import entities as ent
from trendin.spark.extract import morphology as mp

SECTION = "extract"

# 실데이터에서 다시 재야 해 `base.yaml` 이 `null` 로 두는 키. 전부 있어야 시작한다.
REQUIRED = ("per_document_top_k", "score_floor")

# 추론 장치로 받아들이는 이름 (`extract/entities.py` 의 `resolve_device`). `mps` 는 넣지
# 않는다 — 개발 PC 도 배포도 애플 실리콘이 아니라, 통과시켜 두면 아무도 돌려보지 않은 경로가
# 설정으로 열린다.
_DEVICE = re.compile(r"^(cpu|cuda(:\d+)?|auto)$")


@dataclass(frozen=True, slots=True)
class ExtractThresholds:
    """[04] 의 숫자 전부. 한 곳에 모아 두는 이유는 재확정이 파일 하나를 고치는 일이어야
    하기 때문이다."""

    # 선별 — 문서당 상위 K 이고 점수 하한 이상 ([04 §7]). 점수는 0~1 척도다.
    per_document_top_k: int
    score_floor: float
    # 후보 문자 수 하한·상한 ([04 §5] 2번).
    min_chars: int = 2
    max_chars: int = 40
    # BM25 파라미터. **점수에 들어가지 않고 칸에만 적힌다** (`extract/scoring.py` 의 주석).
    bm25_k1: float = 1.2
    bm25_b: float = 0.75

    @classmethod
    def from_config(cls, config: Config) -> "ExtractThresholds":
        section = config.section(SECTION)
        missing = [key for key in REQUIRED if _lookup(section, key) is None]
        if missing:
            raise ConfigError(
                "extract 임계값이 비어 있다 — 실데이터 분포를 재기 전이면 local.yaml 의 잠정값으로 "
                f"돌린다 ([09 §7] 항목 5): {', '.join(f'extract.{key}' for key in missing)}"
            )
        bm25 = section.get("bm25") or {}
        candidate = section.get("candidate") or {}
        default = cls(per_document_top_k=1, score_floor=0.0)
        return cls(
            per_document_top_k=int(section["per_document_top_k"]),
            score_floor=float(section["score_floor"]),
            min_chars=int(candidate.get("min_chars", default.min_chars)),
            max_chars=int(candidate.get("max_chars", default.max_chars)),
            bm25_k1=float(bm25.get("k1", default.bm25_k1)),
            bm25_b=float(bm25.get("b", default.bm25_b)),
        ).validated()

    def validated(self) -> "ExtractThresholds":
        if self.per_document_top_k < 1:
            raise ConfigError("extract.per_document_top_k 는 1 이상이어야 한다")
        if not 0.0 <= self.score_floor <= 1.0:
            raise ConfigError("extract.score_floor 는 0~1 이어야 한다 — 모델 점수의 척도다")
        if self.min_chars < 1 or self.max_chars < self.min_chars:
            raise ConfigError(
                "extract.candidate.min_chars ≤ max_chars 이고 둘 다 1 이상이어야 한다"
            )
        return self


@dataclass(frozen=True, slots=True)
class DomainOptions:
    """[04 §8] — 같은 코드에 설정만 다르게. `extract.domains.{domain}` 에서 온다.

    도메인이 다른 것은 **라벨 목록**뿐이다. 옛 경로의 `code_identifiers` ·
    `hashtag_weight` · `surface_policy` 는 전부 토크나이저의 옵션이었고, 토크나이저가
    없어지면서 같이 없어졌다.
    """

    labels: tuple[str, ...] = ent.FASHION_LABELS

    @classmethod
    def from_config(cls, config: Config, *, domain: str) -> "DomainOptions":
        section = config.section(f"{SECTION}.domains.{domain}")
        labels = section.get("labels")
        if not labels:
            return cls(labels=ent.labels_for(domain))
        if not isinstance(labels, list) or not all(isinstance(item, str) for item in labels):
            raise ConfigError(f"extract.domains.{domain}.labels 는 문자열 목록이어야 한다")
        return cls(labels=tuple(labels))


def recognizer_spec(config: Config, *, domain: str) -> ent.RecognizerSpec:
    """`extract.recognizer` 구역 + 도메인 라벨 → 인식기 설정.

    **모델 이름을 설정으로 뺀 이유** — 일본어의 절 문제를 다른 모델이 푸는지 아직 모른다
    (`scratchpad/kwlab/MULTILINGUAL.md` §7). 바꿔 보는 것이 코드 수정이 아니라 설정 한 줄이어야
    한다.
    """
    section = config.section(f"{SECTION}.recognizer")
    default = ent.RecognizerSpec()
    chunk = section.get("chunk") or {}
    if not isinstance(chunk, dict):
        raise ConfigError("extract.recognizer.chunk 는 표여야 한다")
    batch = section.get("batch") or {}
    if not isinstance(batch, dict):
        raise ConfigError("extract.recognizer.batch 는 표여야 한다")
    spec = ent.RecognizerSpec(
        model=str(section.get("model", default.model)),
        labels=DomainOptions.from_config(config, domain=domain).labels,
        threshold=float(section.get("threshold", default.threshold)),
        chunk_words=int(chunk.get("words", default.chunk_words)),
        chunk_overlap=int(chunk.get("overlap", default.chunk_overlap)),
        max_chunks=int(chunk.get("max_chunks", default.max_chunks)),
        batch_words=int(batch.get("words", default.batch_words)),
        batch_size=int(batch.get("size", default.batch_size)),
        device=str(section.get("device", default.device)),
        precision=str(section.get("precision", default.precision)),
    )
    # **여기서 막지 않으면 증상이 "후보가 줄었다" 로만 나타난다.** 겹침이 예산 이상이면
    # 토막이 앞으로 나아가지 못하고, 예산이 0 이면 토막이 서지 않는다.
    if spec.chunk_words < 1 or spec.max_chunks < 1:
        raise ConfigError("extract.recognizer.chunk.words 와 max_chunks 는 1 이상이어야 한다")
    if not 0 <= spec.chunk_overlap < spec.chunk_words:
        raise ConfigError("extract.recognizer.chunk.overlap 은 0 이상 words 미만이어야 한다")
    if spec.batch_words < spec.chunk_words or spec.batch_size < 1:
        raise ConfigError(
            "extract.recognizer.batch.words 는 chunk.words 이상이고 batch.size 는 1 이상이어야 한다"
        )
    # 오타를 여기서 잡는다. torch 는 모르는 장치 이름을 받으면 모델을 적재한 **뒤에** 죽어서,
    # 5초를 기다린 다음에야 `cude` 를 `cuda` 로 고치게 된다.
    if spec.precision not in ("fp32", "fp16"):
        raise ConfigError(
            f"extract.recognizer.precision 은 fp32 또는 fp16 이어야 한다: {spec.precision!r}"
        )
    if not _DEVICE.match(spec.device):
        raise ConfigError(
            f"extract.recognizer.device 는 cpu · cuda · cuda:N · auto 여야 한다: {spec.device!r}"
        )
    return spec


def adapter_spec(config: Config, *, domain: str, directory: str) -> adapters.AdapterSpec:
    """`extract.language` 구역 → 언어별 후처리 설정.

    형태소 분석기 사용자 사전은 그대로 쓴다 — **한국어 성능의 절반이 거기서 온다**
    (`extract/adapters.py` 의 주석). 모르는 브랜드명을 고유명사로 알려 주면 조사 경계가
    제대로 잡힌다.
    """
    section = config.section(f"{SECTION}.language")
    default = adapters.AdapterSpec()
    gates = section.get("labels") or {}
    if not isinstance(gates, dict):
        raise ConfigError("extract.language.labels 는 언어 → 라벨 목록의 표여야 한다")
    label_gates = tuple(
        (lang, tuple(labels))
        for lang, labels in sorted(gates.items())
        if isinstance(labels, list)
    )
    return adapters.AdapterSpec(
        analyzer=mp.AnalyzerSpec(user_words=mp.load_user_words(directory, domain=domain)),
        label_gates=label_gates or default.label_gates,
        ja_max_chars=int(section.get("ja_max_chars", default.ja_max_chars)),
    )


def lexicon_dir(config: Config) -> str:
    """형태소 분석기 사용자 사전이 있는 디렉터리. 읽는 것은 `userdict-{domain}.txt` 뿐이다.

    **불용어·노이즈 사전은 2026-09-17 에 지웠다** — 라벨이 무엇이 키워드인지 정의하므로 뺄
    것을 셀 필요가 없고, 읽는 코드가 사라진 뒤로 파일만 남아 있었다.
    """
    return str(config.get(f"{SECTION}.lexicon_dir", "spark/conf/lexicon"))


def _lookup(section: dict[str, Any], dotted: str) -> Any:
    node: Any = section
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node
