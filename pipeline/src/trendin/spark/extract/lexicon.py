"""불용어 · 노이즈 사전.

규격은 [04 §5](../../../../spark/docs/04-keyword-extraction-spec.md) · §8.

파일은 `spark/conf/lexicon/` 에 있다. 코드 상수가 아닌 이유는 [04 §10] 과 같다 — 목록을 한 줄
고칠 때마다 이미지를 다시 빌드할 수는 없다.

```
lexicon/
├─ stopwords-ko.txt         언어별 불용어. 구간 경계이자 단독 후보 제외 ([04 §3·§5])
├─ stopwords-en.txt
├─ stopwords-{domain}.txt   도메인 불용어. `code` · `구매` 같은 무정보어 ([04 §8])
└─ noise-{domain}.txt       노이즈 사전. 파일 확장자 · HTTP 상태 · 흔한 변수명 · 쇼핑 상투어
```

**보호어 파일은 없어졌다** (2026-09-09, 형태소 분석기 도입). 조사 규칙이 고유명사를 자르는
일이 없어졌으므로 "자르지 말라" 는 목록이 필요 없다. 분석기가 **모르는** 고유명사를 알려
주는 일은 성격이 달라 사용자 사전으로 옮겼다 — `userdict-{domain}.txt`,
`extract/morphology.py`.

**불용어 목록이 짧아졌다.** 옛 목록의 절반은 조사·어미를 뗀 뒤 남는 서술어 어간(`있` · `하` ·
`보`)과 의존명사(`것` · `수` · `등`)였는데, 형태소 분석기가 그것들을 **후보로 만들지 않으므로**
목록에 둘 이유가 없다 ([04 §5]). 남는 것은 품사가 명사인데 무정보인 낱말이다 — `컬러` · `룩` ·
`구매`.

**초기 목록은 표준 불용어에서 시작하고, DF 상한에 걸린 후보를 검토해 도메인 불용어로 승격한다**
([04 §5]). 손으로 처음부터 쓰지 않는다 — 자동 발견 방식의 부산물이 더 정확하다. 그래서 지금
파일은 씨앗이고, S6 가 실데이터로 채운다.

**모든 항목은 비교키로 저장·대조한다** (`keys.normalized_key`). 파일에 `Code` 로 적어도
`code` 와 맞고, `multi-agent` 로 적어도 `multi agent` 와 맞는다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1). UDF 클로저에 들어가므로 작아야 한다 — 수백
줄짜리 목록은 태스크마다 직렬화돼도 문제없다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from trendin.spark.extract.keys import normalized_key

# 언어별 불용어는 언어와 무관하게 합쳐 쓴다 — `mixed` 문서가 둘 다 필요하고, `ko` 문서에도
# 영문 불용어(`the`, `of`)가 브랜드명 사이에 끼어 온다.
LANGS = ("ko", "en")

STOPWORDS_PREFIX = "stopwords"
NOISE_PREFIX = "noise"


@dataclass(frozen=True, slots=True)
class Lexicon:
    """한 도메인의 사전 셋. 값은 전부 비교키다."""

    stopwords: frozenset[str] = field(default_factory=frozenset)
    noise: frozenset[str] = field(default_factory=frozenset)

    def is_stopword(self, key: str) -> bool:
        return key in self.stopwords

    def is_noise(self, key: str) -> bool:
        return key in self.noise

    @classmethod
    def of(
        cls,
        stopwords: tuple[str, ...] | list[str] | set[str] = (),
        noise: tuple[str, ...] | list[str] | set[str] = (),
    ) -> "Lexicon":
        """테스트와 단발 실행용. 파일 없이 목록을 바로 넣는다."""
        return cls(stopwords=frozenset(_keys(stopwords)), noise=frozenset(_keys(noise)))


def read_terms(path: Path, *, required: bool) -> list[str]:
    """공백으로 나뉜 항목들. `#` 뒤는 주석, 빈 줄은 무시.

    **항목은 토큰 하나다.** 불용어는 구간 경계라 본디 토큰 단위고, 노이즈는 n-gram 의 모든
    토큰이 걸릴 때만 적용된다(`filters.rejection_reason`) — 그래서 여러 단어짜리 항목이
    필요 없고, 한 줄에 여럿 적을 수 있게 공백을 구분자로 쓴다.

    `#` 을 주석으로 쓰면 해시태그를 항목으로 적을 수 없는데, 그래도 되는 이유는 비교키가
    `#` 을 떼기 때문이다 (`keys.normalized_key`) — 해시태그 불용어는 본문 표기로 적는다.
    """
    if not path.exists():
        if required:
            raise FileNotFoundError(f"사전 파일이 없다: {path}")
        return []
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            terms.extend(entry.split())
    return terms


def load_lexicon(directory: Path | str, *, domain: str) -> Lexicon:
    """`{directory}/` 의 파일들에서 한 도메인의 사전을 만든다.

    언어별 불용어 파일은 **필수**다 — 없으면 불용어 경계가 사라져 문장 전체가 한 구간이 되고,
    후보가 조합적으로 늘어 조용히 잡음이 된다. 도메인 파일은 없어도 된다 — 새 도메인이
    붙을 때 빈 목록으로 시작하는 것이 정상이다.
    """
    base = Path(directory)
    stopwords: list[str] = []
    for lang in LANGS:
        stopwords.extend(read_terms(base / f"{STOPWORDS_PREFIX}-{lang}.txt", required=True))
    stopwords.extend(read_terms(base / f"{STOPWORDS_PREFIX}-{domain}.txt", required=False))
    noise = read_terms(base / f"{NOISE_PREFIX}-{domain}.txt", required=False)
    return Lexicon.of(stopwords=stopwords, noise=noise)


def _keys(terms) -> list[str]:
    keys = (normalized_key(term) for term in terms)
    return [key for key in keys if key]
