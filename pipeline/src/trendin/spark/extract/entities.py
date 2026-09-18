"""실체 인식기 — 후보를 만드는 곳 ([04 §2]).

**무엇이 키워드인지를 라벨이 정의한다.** 불용어 사전도 노이즈 사전도 점수 축도 없다.
인식할 유형을 문자열 목록으로 선언하면 모델이 그 유형의 구간만 돌려준다.

## 왜 규칙과 사전을 버렸나

2026-09-16 정제 문서 200건 · 사람이 만든 정답 20건에서 22가지 방법을 같은 기준으로 쟀다
(`scratchpad/kwlab/RESULTS.md`). 옛 경로(BM25 + C-value + 다섯 축 가중합 + 사전 8파일)가
F1 0.233 이고 **순수 TF-IDF 40줄이 소수점 셋째 자리까지 같은 값**을 냈다. 같은 표본에서
GLiNER 는 0.504 로 2.16배다.

코퍼스 순위표로 보면 차이가 더 분명하다 (`RANKED.md`) — 옛 경로의 상위 20 중 아홉 자리가
`가을` · `신발` · `사람` · `요즘` 같은 무정보어이고 다섯 자리가 `Getty` · `Images` ·
`Launchmetrics` 처럼 사진 출처의 조각이다. 실체 인식으로 바꾸면 그 자리가 브랜드와 인물로
채워진다.

## 라벨은 한 벌이다

라벨을 한국어 · 영어 · 일본어로 바꿔 넣고 같은 문서를 재 봤더니 뽑힌 구간이 사실상 같았다
(`scratchpad/kwlab/MULTILINGUAL.md` §1). 모델이 라벨을 문자열이 아니라 의미로 읽는다는
뜻이라, **언어가 늘어도 라벨 목록을 번역해 관리할 필요가 없다.** 사전이 언어마다 느는
구조가 사라지는 것이 이 교체의 본질이다.

## 색상을 뺀 이유

색상 라벨은 정밀도 0.35 인데 기사마다 쏟아져 상위 열 자리를 먹는다. 빼면 F1 이 0.470 →
0.504 로 오른다. 라벨을 더 잘게 쪼개는 것(8 → 13~14개)은 값이 없었다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterator, Sequence

from trendin.spark.extract import chunking as ck

# 패션 도메인의 라벨. **순서가 뜻을 갖지 않는다.**
#
# 색상은 일부러 뺐다 (위 주석). 라벨을 바꾸면 모든 언어가 같이 바뀌므로, 바꿀 때는
# `scratchpad/kwlab` 의 정답으로 전 언어를 다시 재야 한다.
FASHION_LABELS = (
    "브랜드",
    "의류 품목",
    "소재",
    "패션 스타일",
    "인물",
    "컬렉션 또는 행사",
)

# 개발 도메인. 같은 코드에 라벨만 다르다 ([04 §8]).
DEV_LABELS = (
    "프로그래밍 언어",
    "라이브러리 또는 프레임워크",
    "도구 또는 서비스",
    "기술 개념",
    "회사 또는 조직",
    "인물",
)

LABELS_BY_DOMAIN = {"fashion": FASHION_LABELS, "dev": DEV_LABELS}

# 고유명사로 보는 라벨. `is_proper` 축이 여기서 온다 — 옛 경로가 형태소 분석기의 `NNP` 로
# 추정하던 값이고, Kiwi 의 `NNP` 는 신뢰도가 낮았다 (`디올`=NNG · `퍼플`=NNP).
PROPER_LABELS = frozenset({"브랜드", "인물", "회사 또는 조직", "컬렉션 또는 행사"})


@dataclass(frozen=True, slots=True)
class RecognizerSpec:
    """인식기를 만드는 데 필요한 것 전부. **작고 해시 가능해야 한다** — UDF 클로저로
    직렬화되고 `recognizer_for` 의 캐시 키가 된다 (`morphology.AnalyzerSpec` 과 같은 이유).

    모델 자체는 여기 없다. torch 모듈은 pickle 되지 않고, 209M 파라미터를 태스크마다
    보내는 배선이 된다.
    """

    model: str = "urchade/gliner_multi-v2.1"
    labels: tuple[str, ...] = FASHION_LABELS
    # 이 값 미만의 구간은 모델이 돌려주지 않는다. **낮게 잡고 뒤에서 거른다** — 높은 문턱은
    # 추론을 다시 해야 바꿀 수 있지만, 낮게 뽑아 두면 어떤 문턱도 걸러내기만 하면 된다.
    threshold: float = 0.15
    # 토막 하나의 **모델 토큰 수** (`chunking.count_tokens`). ⚠️ 어절이 아니다 — 기호가
    # 따로 세어져 한국어에서 어절의 약 1.5배다. 상한 384 를 다 채우지 않는 것은 서브워드가
    # 다시 2.9~3.2배로 부풀어 자기 주의 비용이 커지기 때문이다.
    chunk_words: int = 256
    # 토막 사이 겹침 토큰 수. 약 9% 로, 업계 권고 10~20% 의 하단이다. 문장 경계에서 끊으므로
    # 낮게 시작하고, 경계에서 놓치는 실체가 관측되면 올린다.
    chunk_overlap: int = 24
    # 문서 하나가 쓸 수 있는 토막 수. **옛 `max_chars` 가 하려던 비용 상한 자리다** — 그 값은
    # 384 어절보다 뒤에 있어 아무 일도 하지 않았다. 256×3 이면 약 2,800자를 본다.
    max_chunks: int = 3
    # 한 배치의 토큰 예산. **문서 수가 아니라 토큰 수로 잡는다** — 짧은 토막과 긴 토막을
    # 같은 배치에 넣으면 짧은 쪽이 긴 쪽 길이로 패딩되어 헛돈다.
    # 표본 138건에서 이 배칭만으로 1.37배 빨라졌고 결과는 구간 수까지 동일했다.
    batch_words: int = 2048
    # 한 배치의 토막 수 상한. 예산이 남아도 이보다 많이 넣지 않는다 — 짧은 토막만 모이면
    # 배치가 무한정 커져 메모리를 삼킨다.
    batch_size: int = 32
    # 추론을 올릴 장치. `cpu` · `cuda` · `cuda:N` · `auto` 중 하나다.
    #
    # **기본이 `cpu` 인 것은 배포가 CPU 이기 때문이다** — 데이터 EC2 에 GPU 가 없고, 이미지도
    # torch 를 CPU 휠로 깐다 (`spark/versions.sh`). `auto` 는 쓸 수 있으면 쓰는 값이라 편하지만
    # 기본으로 두지 않는다. GPU 가 있는 개발 PC 와 없는 서버가 **같은 설정으로 다르게 돌면**,
    # 로컬에서 재현되지 않는 성능 차이의 원인을 설정에서 찾을 수 없게 된다.
    #
    # ⚠️ **`cuda` 는 워커 하나를 전제한다.** 모델이 executor 파이썬 프로세스마다 적재되므로
    # (`recognizer_for`) 워커가 여럿이면 같은 수의 사본이 VRAM 에 올라간다. 209M 파라미터가
    # fp32 로 약 840 MB 라 6 GB 짜리 GPU 에서도 넷을 넘기면 터진다. 막는 자리는
    # `extract/batch.py` 의 `_partition_count` 다.
    device: str = "cpu"
    # 가중치의 수치 정밀도. `fp32` · `fp16` 중 하나다.
    #
    # **fp16 은 GPU 에서만 뜻이 있다.** Ada 세대는 반정밀도 텐서 코어를 갖고 있어 같은 일을
    # 절반의 메모리로 두 배 빠르게 한다 — 2026-09-17 실측(문서 100건)에서 9.98초·2.33GB 가
    # 6.43초·1.21GB 였다. **메모리가 절반인 것이 속도보다 중요하다** — 6 GB 짜리 GPU 에서
    # fp32 는 VRAM 을 96%까지 채우고, 그 뒤로는 할당자가 매번 재조정하느라 대역폭이 0% 로
    # 떨어져 건당 2.3초, 곧 CPU(467ms)보다 느려졌다.
    #
    # ⚠️ **결과가 완전히 같지는 않다.** 같은 실측에서 구간이 3,481개 대 3,475개로 0.2%
    # 달랐다. 문턱 근처의 구간이 갈린 것이고, 그 뒤에 점수 하한([04 §7])이 한 번 더 있어
    # 선별까지 가는 영향은 더 작다. 그래도 **운영 기본은 fp32 다** — 배포는 CPU 라 fp16 이
    # 이득도 없이 결과만 흔든다.
    precision: str = "fp32"


@dataclass(frozen=True, slots=True)
class Span:
    """인식된 구간 하나. **원문 안의 위치를 들고 간다** — 언어별 후처리가 경계를 다시
    잡을 때 필요하다 (`extract/adapters.py`)."""

    surface: str
    label: str
    score: float
    start: int
    end: int

    @property
    def is_proper(self) -> bool:
        return self.label in PROPER_LABELS


AUTO_DEVICE = "auto"
FP16 = "fp16"


def resolve_device(device: str) -> str:
    """설정의 장치 이름 → torch 가 받는 장치 이름.

    **`auto` 만 여기서 갈린다.** `cuda` 를 달라고 했는데 없으면 CPU 로 되돌리지 않고 그대로
    넘겨서 torch 가 죽게 둔다 — GPU 를 쓰겠다고 명시한 실행이 조용히 CPU 로 돌면, 하루치가
    열 배 걸리는 것 말고는 아무 신호가 없다.

    torch 를 여기서 import 하는 것은 `registry/embedding.py` 와 같은 이유다. 모듈을 import
    하는 것만으로 torch 가 올라오면 층 1 테스트가 800 MB 를 끌고 온다.
    """
    name = (device or "cpu").strip().lower()
    if name != AUTO_DEVICE:
        return name
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


class Recognizer:
    """GLiNER 하나를 감싼다. **`Span` 만 내보낸다** — gliner 타입이 이 파일 밖으로 나가지
    않아야 층 1 테스트가 인식기를 흉내 낼 수 있다 (`morphology.Analyzer` 와 같은 규약).
    """

    def __init__(self, spec: RecognizerSpec) -> None:
        from gliner import GLiNER

        self._spec = spec
        self._model = GLiNER.from_pretrained(spec.model)
        # **적재 뒤에 옮긴다.** `from_pretrained` 에 `map_location` 을 주는 길도 있지만, 그
        # 인자는 gliner 판올림에서 이름이 바뀐 이력이 있고 `.to()` 는 torch 의 규약이라
        # 흔들리지 않는다. 옮기지 못하면 여기서 죽어야 한다 — CPU 로 조용히 되돌아가면
        # 증상이 "GPU 를 붙였는데 안 빨라졌다" 로만 나타난다.
        self.device = resolve_device(spec.device)
        if self.device != "cpu":
            self._model.to(self.device)
        # **CPU 에서는 걸지 않는다.** 반정밀도 커널이 CPU 에 거의 없어 오히려 느려지고,
        # 배포가 CPU 라 그 경로로 결과가 흔들리면 안 된다.
        if spec.precision == FP16 and self.device != "cpu":
            self._model.half()
        # 추론만 한다. dropout 이 켜져 있으면 같은 문서가 실행마다 다른 값을 받는다.
        self._model.eval()

    def predict(self, texts: Sequence[str]) -> list[list[Span]]:
        """문서 묶음 → 문서마다 구간 목록. **묶음으로 받는 이유가 이 클래스의 전부다** —
        트랜스포머는 배치로 넣어야 세션 비용이 문서 수로 나뉜다.

        토막을 여기서 내고 여기서 되돌린다. 부르는 쪽이 자르면 `start`·`end` 가 원문과
        어긋나고, 그 값에 제목 가산과 조사 제거가 걸려 있다 (`extract/chunking.py`).
        **밖에서 본 계약은 바뀌지 않는다** — 문서를 넣고 문서별 구간을 받는다.
        """
        if not texts:
            return []
        spec = self._spec
        units: list[tuple[ck.Chunk, int]] = []  # (토막, 그 토막이 나온 문서 번호)
        for index, text in enumerate(texts):
            for chunk in ck.split(
                text or "",
                budget=spec.chunk_words,
                overlap=spec.chunk_overlap,
                max_chunks=spec.max_chunks,
            ):
                units.append((chunk, index))

        spans: list[list[Span]] = [[] for _ in texts]
        for batch in _packed(units, budget=spec.batch_words, size=spec.batch_size):
            found = self._predict_chunk([units[i][0].text for i in batch])
            for position, entities in zip(batch, found):
                chunk, index = units[position]
                # 토막 안의 위치를 원문 위치로 옮긴다. **이 한 줄이 제목 가산과 꼬리 제거를
                # 지킨다.**
                spans[index].extend(
                    replace(span, start=span.start + chunk.offset, end=span.end + chunk.offset)
                    for span in entities
                )
        return [_dedupe(found) for found in spans]

    def _predict_chunk(self, texts: list[str]) -> list[list[Span]]:
        """배치 하나를 모델에 넣는다. **한 묶음이 죽어도 나머지를 죽이지 않는다** — 문서
        하나의 인코딩 문제로 하루치 추출이 실패하면 안 되고, 빈 결과는
        `documents_without_candidates` 통계에 잡힌다 ([04 §9]).

        ⚠️ **이 except 가 조용한 실패의 통로다.** 추론이 통째로 죽어도(`SparkContext was
        shut down`) 여기서 빈 결과가 나가고 Job 은 정상으로 끝난다. 층 1 이라 로그를 남길
        수 없으므로(이 층은 `common/logging` 을 import 하지 않는다) **막는 자리는
        `jobs/extract.py` 다** — 대상이 있는데 적재가 0건이면 거기서 실패로 끝낸다.
        이 except 를 좁히거나 없앨 때는 그쪽 검사도 함께 본다.
        """
        try:
            batches = self._model.batch_predict_entities(
                texts, list(self._spec.labels), threshold=self._spec.threshold
            )
        except Exception:  # noqa: BLE001 — 모델 쪽 예외 종류를 이 층이 알 수 없다
            return [[] for _ in texts]
        return [
            [
                Span(
                    surface=entity["text"],
                    label=entity["label"],
                    score=float(entity["score"]),
                    start=int(entity["start"]),
                    end=int(entity["end"]),
                )
                for entity in entities
            ]
            for entities in batches
        ]


def _packed(
    units: list[tuple[ck.Chunk, int]], *, budget: int, size: int
) -> "Iterator[list[int]]":
    """토막 목록 → 배치마다 토막 번호 묶음. **길이가 비슷한 것끼리 담는다.**

    패딩이 배치의 최장 토막에 맞춰지므로 56 어절과 256 어절을 한 배치에 넣으면 짧은 쪽이
    다섯 배를 헛돈다. 표본 138건에서 이 배칭만으로 **1.37배 빨라졌고 구간 수는 한 개도
    달라지지 않았다** — 결과를 바꾸지 않고 얻는 속도다.

    정렬 키에 원래 위치를 함께 넣는다. 같은 길이에서 순서가 흔들리면 배치 구성이 실행마다
    달라지고, 그러면 스냅샷이 서지 않는다 ([04 §9]).
    """
    # **`split()` 이 아니라 `ck.count_tokens` 다** — 모델의 분할 규칙과 같아야 예산이 맞는다.
    lengths = [ck.count_tokens(chunk.text) for chunk, _ in units]
    batch: list[int] = []
    longest = 0
    for index in sorted(range(len(units)), key=lambda i: (lengths[i], i)):
        words = max(1, lengths[index])
        if batch and (max(words, longest) * (len(batch) + 1) > budget or len(batch) >= size):
            yield batch
            batch, longest = [], 0
        batch.append(index)
        longest = max(longest, words)
    if batch:
        yield batch


# 두 구간이 이 비율을 넘게 겹치면 같은 것으로 본다. 겹침 구역을 두 토막이 함께 보므로
# 경계가 한 어절씩 어긋난 쌍이 나온다.
_OVERLAP_RATIO = 0.5


def _dedupe(spans: list[Span]) -> list[Span]:
    """겹침 구역에서 두 번 잡힌 구간을 접는다. **없으면 `tf` 가 부푼다** —
    `extract/document.py` 의 `_merge` 가 반복 출현으로 세어 `REPEAT_BONUS` 를 두 번 준다.
    같은 자리를 두 토막이 본 것이지 문서 안에서 두 번 나온 것이 아니다.

    점수가 높은 것부터 채택한다. **정렬 키에 위치와 표기를 함께 넣는 이유** — 점수만으로
    정렬하면 같은 점수에서 순서가 흔들려 같은 입력이 실행마다 다른 결과를 낸다.
    """
    kept: list[Span] = []
    for span in sorted(spans, key=lambda s: (-s.score, s.start, s.end, s.surface)):
        width = span.end - span.start
        if width <= 0:
            continue
        if any(
            max(0, min(span.end, other.end) - max(span.start, other.start))
            / min(width, other.end - other.start)
            > _OVERLAP_RATIO
            for other in kept
        ):
            continue
        kept.append(span)
    # 등장 순서로 돌려준다 — `_merge` 가 이 순서로 비교키의 첫 등장을 정한다.
    return sorted(kept, key=lambda s: (s.start, s.end))


# 프로세스마다 하나. executor 파이썬 워커가 태스크 사이에 살아남으므로 워커당 한 번 만들어진다
# (`spark.python.worker.reuse` 가 기본 참). `morphology._CACHE` 와 같은 구조다.
_CACHE: dict[RecognizerSpec, Recognizer] = {}


def recognizer_for(spec: RecognizerSpec) -> Recognizer:
    """`spec` 에 해당하는 인식기. **같은 프로세스에서는 한 번만 만든다.**

    적재가 약 5초다. 파티션마다 만들면 그 값이 파티션 수만큼 곱해지고, 문서마다 만들면
    배치가 서지 않는다.
    """
    recognizer = _CACHE.get(spec)
    if recognizer is None:
        recognizer = Recognizer(spec)
        _CACHE[spec] = recognizer
    return recognizer


def labels_for(domain: str) -> tuple[str, ...]:
    """도메인의 기본 라벨. 모르는 도메인은 패션 라벨을 쓴다 — 라벨이 없으면 모델이 아무것도
    돌려주지 않아 증상이 "후보가 0개" 로만 나타난다."""
    return LABELS_BY_DOMAIN.get(domain, FASHION_LABELS)
