"""형태소 분석기 — 한국어 표기의 품사 판정.

규격은 [04 §2](../../../../spark/docs/04-keyword-extraction-spec.md).

`extract/adapters.py` 가 쓰는 어댑터다. **분석기를 고르고, 만들고, 품사를 역할로 옮기는 일**
셋만 여기 있다. 표기의 꼬리를 어디서 자를지 정하는 것은 저쪽이다.

## 실체 인식으로 옮긴 뒤에도 남은 이유

2026-09-16 에 후보 생성이 GLiNER 로 바뀌었지만 이 파일은 남았다. **다국어 모델이 한국어
어절 경계를 모르기 때문**이다. 회귀 코퍼스 30건의 구운 구간 538개로 분석기를 끄고 재어
보면 후보가 335개에서 419개로 늘어나는데, 늘어난 것이 전부 `디올의` · `디올이` ·
`디올과` · `디올은` 처럼 같은 실체의 조사 변형이다 (`다이아몬드` 하나가 네 후보가 된다).
분석기를 켜면 그 넷이 `디올` 하나로 접힌다.

## 왜 규칙표를 버렸나

2026-09-09 실데이터 373건(fashion 7매체) 종단 실행에서 상위 100 후보를 눈으로 분류했더니
**약 48개가 "품사를 모르는 것" 하나에서 나온 오류**였다 — 조사·어미 잔재 29(`컬러의` ·
`힘을` · `올가을엔`) · 서술어 활용형 19(`더해` · `싶다면` · `부드러운`) · 문장 조각
(`두고 활동한` · `스커트보`). 접미 표(조사 40 · 어미 60 · 최소 어간 문턱 3단 · 보호어 파일)에
패치를 덧붙이는 방식으로는 하루에 새 케이스 다섯 개가 나왔다. 표를 늘리는 것은 사전이 문법을
흉내 내는 일이고, 문법은 이미 만들어져 있다.

## 왜 kiwipiepy 인가

| 후보 | 판정 | 근거 |
| --- | --- | --- |
| **kiwipiepy** | **고른 것** | C++ 확장이라 JVM · torch 가 없다. **휠이 두 OS 다 있다** |
| konlpy (Okt · Komoran) | 아니다 | JPype + JVM. executor 안에 JVM 을 하나 더 띄우는 배선이 된다 |
| python-mecab-ko | 아니다 | **Windows 휠이 없다.** 아래 참조 |
| bareunpy | 아니다 | 서버와 API 키. [00 §4] 가 배제한 외부 API 의존이다 |
| pecab | 아니다 | 순수 파이썬. pyarrow 에 기대고 느리다 — 정확도 이득 없이 의존성만 는다 |
| soynlp | 아니다 | 비지도 단어 추출이라 **품사를 주지 않는다.** 우리 문제가 품사다 |

**Windows 휠이 왜 조건인가** — 층 1 테스트와 스냅샷 갱신은 호스트에서 돈다 ([09 §4]).
호스트가 Windows 인데 분석기가 리눅스에서만 설치되면, 토큰화를 고칠 때마다 컨테이너를
띄워야 하고 층 구분이 무너진다. kiwipiepy 는 두 곳에서 **같은 모델로 같은 결과**를 낸다.

그 밖에 kiwipiepy 를 고른 이유 둘 — 사용자 사전 API(`add_user_word`)로 모르는 브랜드명을
알려 줄 수 있고, 해시태그·URL·이메일을 `W_HASHTAG` · `W_URL` · `W_EMAIL` 로 **분석기가
직접 태깅**해 우리 정규식이 하던 일을 덜어 준다.

대가는 크기다 — `kiwipiepy_model` 이 설치 후 약 110 MB 다. 이미지 한 겹이 그만큼 커진다
(`spark/scripts/build-image.sh` 를 다시 돌려야 한다). 처리량은 1,600자 문서 120건/초
(단일 스레드)라 373건 코퍼스에서 3초 안쪽이고, Spark 배치 시작 비용에 묻힌다.

## Kiwi 객체는 pickle 되지 않는다

`ExtractionOptions` 는 UDF 클로저로 executor 에 직렬화된다 (`extract/batch.py`). Kiwi 는
C++ 핸들을 들고 있어 `pickle.dumps` 가 `TypeError` 로 죽는다. 그래서 **클로저에는 `AnalyzerSpec`
(작고 해시 가능한 설정)만 담고, 분석기는 executor 프로세스에서 처음 필요할 때 만들어
모듈 전역에 캐시한다** (`analyzer_for`). Spark 는 `spark.python.worker.reuse` 가 기본 참이라
파이썬 워커가 태스크 사이에 살아남으므로, 워커당 한 번만 만들어진다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

USERDICT_PREFIX = "userdict"

# --- 품사 → 역할 -------------------------------------------------------------
#
# Kiwi 의 세종 태그셋에서 **명사 핵만** 고른다. 나머지는 전부 경계다 — 그것이 규칙표가
# 하려 했던 일이고, 이제 태그가 대신 한다.

# 명사 핵. 후보 표기를 이루는 알맹이다. `adapters._strip_tail` 이 "이것이 하나도 없으면
# 키워드가 아니다" 로 쓰는 것이 이 집합의 용도 전부다.
NOUN_CORE = frozenset(
    {
        "NNG",  # 일반명사 — `실루엣` · `컬렉션`
        "NNP",  # 고유명사 — `샤넬` · `밀라노`
        "SL",  # 외국어 — `MCP` · `useEffect` · `os.path`
        "SH",  # 한자
        "SN",  # 숫자 — 단독으로는 형태 필터가 막고 `Python 3.12` 의 꼬리로만 산다
    }
)

# 경계로만 쓰는 태그 중 **일부러 뺀 것**. 표에 적어 두는 이유는 "빠뜨린 것" 과 "뺀 것" 을
# 다음 사람이 구분할 수 있어야 하기 때문이다.
#
# | 태그 | 예 | 왜 후보가 아닌가 |
# | --- | --- | --- |
# | NNB | `것` · `수` · `원` | 의존명사. 옛 불용어 목록의 절반이 이것이었다 |
# | NR · NP | `하나` · `우리` | 수사 · 대명사 |
# | VV · VA · VX · VCP | `더하` · `부드럽` | 용언. **실측 오류 19개가 여기서 나왔다** |
# | XSV · XSA | `하` (`매치해`) | 용언 파생 접미사 |
# | MM · MAG · MAJ · IC | `첫` · `그리고` | 수식언 · 접속 · 감탄 |
# | JKS · JKO · JKG · JX · JC | `이` · `를` · `의` | 조사. **실측 오류 29개** |
# | EF · EC · ETM · ETN · EP | `다` · `며` · `ᆫ` | 어미 |
# | SF · SP · SS · SE · SO · SW | `.` · `,` · `(` | 부호 |
# | W_URL · W_EMAIL · W_MENTION | | [03 §4] 가 지웠다. 남아 오면 경계 |
# | XR | `깨끗` | 어근. 홀로는 낱말이 아니다 |


@dataclass(frozen=True, slots=True)
class Morph:
    """형태소 하나. `start`·`end` 는 **원문 안의 위치**다 — 표기를 원문에서 잘라 오려고 든다.

    분석기가 주는 `form` 은 기본형이라 원문과 다를 수 있다 (`부드러운` → `부드럽`). 후보
    표기는 화면에 나가는 값이므로 기본형이 아니라 원문 조각이어야 한다.
    """

    tag: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class AnalyzerSpec:
    """분석기를 만드는 데 필요한 것 전부. **작고 해시 가능해야 한다** — UDF 클로저로
    직렬화되고 `analyzer_for` 의 캐시 키가 된다.

    `user_words` 가 튜플인 이유가 그것이다. 정렬해 두면 같은 사전이 같은 키가 된다.
    """

    # `(표기, 품사)`. 대개 `NNP` 다 — 분석기가 모르는 브랜드명을 고유명사로 알려 준다.
    user_words: tuple[tuple[str, str], ...] = ()


class Analyzer:
    """Kiwi 한 개를 감싼다. **`Morph` 만 내보낸다** — kiwipiepy 타입이 이 파일 밖으로
    나가지 않아야 층 1 테스트가 분석기를 흉내 낼 수 있다.
    """

    def __init__(self, spec: AnalyzerSpec) -> None:
        from kiwipiepy import Kiwi

        self._kiwi = Kiwi()
        for surface, tag in spec.user_words:
            self._kiwi.add_user_word(surface, tag)

    def analyze(self, lines: Sequence[str]) -> list[list[Morph]]:
        """줄마다 형태소 목록. **줄 단위로 부르는 이유** — 줄바꿈은 구간 경계다
        ([03 §4] 가 문장 경계 정보로 줄바꿈 하나를 남긴 이유). 목록으로 한 번에 넘겨
        호출 비용을 줄인다.
        """
        if not lines:
            return []
        result: list[list[Morph]] = []
        for tokens in self._kiwi.tokenize(list(lines)):
            result.append(
                [Morph(token.tag, token.start, token.start + token.len) for token in tokens]
            )
        return result


# 프로세스마다 하나. executor 파이썬 워커가 태스크 사이에 살아남으므로 워커당 한 번 만들어진다.
_CACHE: dict[AnalyzerSpec, Analyzer] = {}


def analyzer_for(spec: AnalyzerSpec) -> Analyzer:
    """`spec` 에 해당하는 분석기. **같은 프로세스에서는 한 번만 만든다.**

    문서마다 만들면 초기화(약 0.8초)가 문서 수만큼 곱해져 배치가 서지 않는다. 캐시를
    비우는 길을 두지 않은 이유는 spec 이 Job 실행 하나 안에서 고정이고, 워커 프로세스가
    실행보다 오래 살지 않기 때문이다.
    """
    analyzer = _CACHE.get(spec)
    if analyzer is None:
        analyzer = Analyzer(spec)
        _CACHE[spec] = analyzer
    return analyzer


def load_user_words(directory: Path | str, *, domain: str) -> tuple[tuple[str, str], ...]:
    """`{directory}/userdict-{domain}.txt` → `(표기, 품사)` 목록. 없으면 빈 목록.

    형식은 한 줄에 하나, `표기` 또는 `표기<탭 또는 공백>품사`. 품사를 적지 않으면 `NNP` 다.
    `#` 뒤는 주석.

    **항목을 비교키로 접지 않는다** — 분석기에게 알려 주는 것은 원표기다. `샤넬` 을
    `샤넬` 로 알려 줘야 하고 `chanel` 로는 뜻이 없다.
    """
    path = Path(directory) / f"{USERDICT_PREFIX}-{domain}.txt"
    if not path.exists():
        return ()
    words: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if not entry:
            continue
        parts = entry.split()
        surface = parts[0]
        tag = parts[1] if len(parts) > 1 else "NNP"
        words.append((surface, tag))
    return tuple(sorted(set(words)))
