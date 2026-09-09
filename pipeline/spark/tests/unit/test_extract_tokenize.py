"""언어별 토큰화 ([04 §2]). 층 1 ([09 §4]).

한국어는 **형태소 분석기로 품사를 보고 명사만 남긴다** (2026-09-09). 여기서 보는 것은
(a) 조사·어미·용언·의존명사가 경계가 되고 후보의 재료가 아닌지 (b) 표기를 원문에서 잘라
오는지 (c) 표기 정책 세 값이 뜻대로 갈리는지 (d) 사용자 사전이 고유명사를 살리는지
(e) 영문 식별자·버전·약어 규칙이 **그대로인지**다.

**형태소 분석기가 층 1 에 있는 것이 맞다.** kiwipiepy 는 pyspark 를 끌어오지 않고 Windows
호스트에서 돈다 — 그게 [09 §4] 층 구분을 지키려고 그 분석기를 고른 이유다
(`extract/morphology.py` 의 표).
"""

from __future__ import annotations

import pickle

import pytest

from trendin.spark.extract import morphology as mp
from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.lexicon import Lexicon
from trendin.spark.extract.tokenize import TokenizeOptions, tokenize
from trendin.spark.normalize.lang import EN, KO, MIXED

LEXICON = Lexicon.of(stopwords=["the", "is", "and", "of", "이번", "것", "컬러"])

# 사용자 사전을 쓰는 시험만 이 spec 을 쓴다. 나머지는 기본 spec 이라 분석기가 한 번만 만들어진다.
BRANDS = mp.AnalyzerSpec(user_words=(("발렌시아가", "NNP"), ("오프화이트", "NNP")))


def surfaces(tokens):
    return [token.surface for token in tokens]


def boundaries(tokens):
    return [token.surface for token in tokens if token.boundary_after]


def ko(text, *, lexicon=LEXICON, **kwargs):
    return tokenize(text, KO, lexicon=lexicon, options=TokenizeOptions(**kwargs))


# --- 한국어 — 조사·어미는 후보의 재료가 아니다 --------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("코트를", ["코트"]),
        ("실루엣의", ["실루엣"]),
        ("컬렉션을", ["컬렉션"]),
        ("밀라노에서", ["밀라노"]),
        ("브랜드는", ["브랜드"]),
        ("컬렉션에서는", ["컬렉션"]),
        # 규칙표 시절 문턱으로 지켜야 했던 것들. 이제 품사가 지킨다.
        ("런웨이", ["런웨이"]),
        ("평가", ["평가"]),
        ("가을", ["가을"]),
        ("프라다", ["프라다"]),
        ("캐나다", ["캐나다"]),
    ],
)
def test_조사를_뗀_명사만_남는다(text, expected):
    assert surfaces(ko(text)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 명사 + `하다/되다` 서술어 → 명사만 남는다.
        ("공개했다", ["공개"]),
        ("재해석한", ["재해석"]),
        ("미니멀한", ["미니멀"]),
        ("매치해", ["매치"]),
        # 활용형은 사라지고 명사만 남는다. 규칙표 시절 `등장했고` · `조합이에요` 가 **활용형
        # 그대로** 상위 100 에 올라왔다 (실측 오류 19개). 남는 명사가 무정보하면 그건
        # 불용어의 일이고([04 §5]), 활용형 자체가 후보가 되는 것과는 다른 문제다.
        ("등장했고", ["등장"]),
        ("조합이에요", ["조합"]),
        # 어간이 명사가 아닌 순수 용언은 **아무 후보도 내지 않는다.**
        ("부드러운", []),
        ("싶다면", []),
        ("더해", []),
        ("앞세웠다고", []),
    ],
)
def test_용언은_후보가_되지_않는다(text, expected):
    assert surfaces(ko(text)) == expected


@pytest.mark.parametrize("text", ["것은", "것으로", "우리는"])
def test_의존명사와_대명사는_품사가_거른다(text):
    """[04 §5] 의 옛 불용어 목록 절반이 이것이었다 — 사전이 아니라 품사가 거른다.
    `것`(NNB) · `우리`(NP) 는 토큰조차 되지 않는다."""
    assert ko(text) == []


@pytest.mark.parametrize("text", ["20대에게", "19만9천원", "2026년"])
def test_수량_표기는_숫자만_남아_후보가_되지_않는다(text):
    """단위(`대` · `원` · `년`)가 NNB 라 떨어지고 숫자만 남는다. 숫자 꼴은 n-gram 의
    꼬리로만 허용되므로(`candidates._valid_window`) 단독 후보가 되지 않는다."""
    assert [token.kind for token in ko(text)] == [tk.NUMBER]


def test_명사이지만_무정보한_낱말은_불용어가_거른다():
    """`하나` 는 품사가 NNG 라 품사로는 걸러지지 않는다 — 규칙표 시절 `하나의`(72문서)가
    상위 100 에 있었던 그 낱말이다. 이제 조사가 갈려 비교키가 `하나` 이고, 사전에 이미
    있던 항목에 **바로 걸린다** ([04 §5])."""
    (token,) = ko("하나의", lexicon=Lexicon.of(stopwords=["하나"]))
    assert (token.surface, token.is_stop) == ("하나", True)


def test_조사_자리가_구간_경계다():
    tokens = ko("인트레치아토 기법을 재해석한 백과 미니멀한 실루엣")

    assert surfaces(tokens) == ["인트레치아토", "기법", "재해석", "백", "미니멀", "실루엣"]
    # `백과` 의 `과` 가 조사로 옳게 갈린다 — 규칙표 시절에는 `백과 미니멀` 이 한 구간이었다.
    assert boundaries(tokens) == ["기법", "재해석", "백", "미니멀", "실루엣"]
    # 조사가 없는 `인트레치아토` 뒤는 열려 있어 `인트레치아토 기법` 이 n-gram 이 된다.
    assert tokens[0].boundary_after is False


def test_명사가_이어지면_한_구간이다():
    """[04 §3] 의 명사 연속. 공백으로 갈린 명사들은 경계 없이 이어져 n-gram 이 된다."""
    tokens = ko("오버사이즈 테일러드 재킷")

    assert surfaces(tokens) == ["오버사이즈", "테일러드", "재킷"]
    assert boundaries(tokens) == ["재킷"]  # 줄 끝뿐


# --- 표기는 원문에서 잘라 온다 -------------------------------------------------


def test_붙여_쓴_복합어는_한_토큰이다():
    """[04 §2] — 형태소가 **공백 없이** 붙어 있으면 한 표기다. `개발자` + `경험` 은 두
    형태소지만 원문에 공백이 없어 `개발자경험` 하나가 된다."""
    assert surfaces(ko("개발자경험 개선")) == ["개발자경험", "개선"]


def test_표기는_기본형이_아니라_원문이다():
    """분석기의 `form` 은 기본형이라 원문과 다르다 (`컬러칩` 은 그대로지만 용언은 바뀐다).
    표기가 화면에 나가는 값이므로 원문 조각이어야 한다 — 위치만 쓰고 문자열은 슬라이스한다."""
    (token,) = ko("스타일링을")
    assert token.surface == "스타일링"


def test_원문에_없는_공백이_표기에_들어가지_않는다():
    """분석기 사전에 공백이 든 항목(`미우 미우`)이 있어도 표기는 원문 그대로다."""
    spec = mp.AnalyzerSpec(user_words=(("미우미우", "NNP"),))
    assert surfaces(ko("미우미우의 백", analyzer=spec))[0] == "미우미우"


# --- 표기 정책 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (mp.SURFACE_CORE, ["해석", "아이템", "패션"]),
        (mp.SURFACE_PREFIXED, ["재해석", "아이템", "패션"]),
        (mp.SURFACE_WORD, ["재해석", "아이템들", "패션계"]),
    ],
)
def test_표기_정책_세_값이_접두_접미를_가른다(policy, expected):
    """`morphology.SURFACE_*`. 2026-09-09 에 셋을 실데이터로 돌려 비교하고 `prefixed` 를
    골랐다 ([04 §2] 의 표) — 그 비교를 되돌릴 수 있게 설정으로 남겼다."""
    tokens = ko("재해석한 아이템들은 패션계의", surface_policy=policy)
    assert surfaces(tokens) == expected


def test_기본_정책은_prefixed():
    assert TokenizeOptions().surface_policy == mp.SURFACE_PREFIXED


# --- 사용자 사전 ---------------------------------------------------------------


def test_사용자_사전이_없으면_고유명사가_조사째_남는다():
    """분석기가 모르는 브랜드의 대가다. **옛 보호어 파일과 반대 방향**이다 — 자르는 것이
    아니라 못 자르는 것이 문제다 ([04 §2])."""
    assert surfaces(ko("발렌시아가와 오프화이트의")) != ["발렌시아가", "오프화이트"]


def test_사용자_사전이_고유명사를_살린다():
    tokens = ko("발렌시아가와 오프화이트의 협업", analyzer=BRANDS)

    assert surfaces(tokens) == ["발렌시아가", "오프화이트", "협업"]
    # 조사가 갈렸으므로 그 자리가 경계다 — `발렌시아가 오프화이트` n-gram 이 생기지 않는다.
    assert boundaries(tokens) == ["발렌시아가", "오프화이트", "협업"]


def test_사용자_사전_파일은_품사를_생략할_수_있다(tmp_path):
    (tmp_path / "userdict-fashion.txt").write_text(
        "# 주석\n샤넬\n르메르 NNP\n\n구찌   # 꼬리 주석\n", encoding="utf-8"
    )
    assert mp.load_user_words(tmp_path, domain="fashion") == (
        ("구찌", "NNP"),
        ("르메르", "NNP"),
        ("샤넬", "NNP"),
    )


def test_사용자_사전_파일이_없으면_빈_목록(tmp_path):
    assert mp.load_user_words(tmp_path, domain="fashion") == ()


# --- UDF 배선 ------------------------------------------------------------------


def test_분석기_설정은_pickle_되고_분석기는_안_된다():
    """**배선 회귀.** `TokenizeOptions` 는 UDF 클로저로 executor 에 직렬화된다
    (`extract/batch.py`). 여기에 Kiwi 가 들어가면 Job 이 `TypeError` 로 죽는다 —
    그래서 설정만 담고 분석기는 executor 에서 만든다 (`morphology.analyzer_for`).
    """
    pickle.loads(pickle.dumps(TokenizeOptions(analyzer=BRANDS)))

    with pytest.raises(TypeError):
        pickle.dumps(mp.analyzer_for(BRANDS)._kiwi)


def test_같은_설정이면_분석기를_다시_만들지_않는다():
    """문서마다 만들면 초기화 0.8초가 문서 수만큼 곱해진다."""
    assert mp.analyzer_for(BRANDS) is mp.analyzer_for(mp.AnalyzerSpec(user_words=BRANDS.user_words))
    assert mp.analyzer_for(BRANDS) is not mp.analyzer_for(mp.AnalyzerSpec())


# --- 불용어 --------------------------------------------------------------------


def test_불용어는_표시만_하고_토큰으로_남긴다():
    """BM25 의 문서 길이는 불용어까지 센다 — 구간을 자르는 것은 `candidates.spans` 의 일이다."""
    tokens = tokenize("the agentic workflow is here", EN, lexicon=LEXICON)

    assert [t.is_stop for t in tokens] == [True, False, False, True, False]
    assert tk.doc_length(tokens) == 5


def test_불용어_대조에_어간_규칙이_필요_없어졌다():
    """규칙표 시절 `컬러의`(83문서) 가 사전을 우회했다 — 어간이 짧아 조사를 떼지 않아
    비교키가 `컬러의` 였고 사전에 걸리지 않았다 ([04 §5]). 이제 분석기가 조사를 떼고 오므로
    비교키가 `컬러` 이고 **한 번만 대조하면 걸린다.**
    """
    tokens = ko("가을 컬러의 조합")

    assert surfaces(tokens) == ["가을", "컬러", "조합"]
    assert [t.is_stop for t in tokens] == [False, True, False]


# --- 영어 — 규칙이 그대로다 -----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "surface", "kind"),
    [
        ("useEffect", "useEffect", tk.CODE),
        ("snake_case", "snake_case", tk.CODE),
        ("os.path", "os.path", tk.CODE),
        ("multi-agent", "multi-agent", tk.WORD),
        ("3.12", "3.12", tk.VERSION),
        ("v2", "v2", tk.VERSION),
        ("ES2023", "ES2023", tk.VERSION),
        ("MCP", "MCP", tk.ACRONYM),
        ("R&D", "R&D", tk.ACRONYM),
        ("C++", "C++", tk.WORD),
        ("C#", "C#", tk.WORD),
        ("2026", "2026", tk.NUMBER),
        ("29,000", "29,000", tk.NUMBER),
        ("#vibecoding", "#vibecoding", tk.HASHTAG),
    ],
)
def test_식별자_버전_약어_해시태그를_한_토큰으로_보존한다(text, surface, kind):
    tokens = tokenize(text, EN, lexicon=LEXICON)
    assert [(t.surface, t.kind) for t in tokens] == [(surface, kind)]


def test_원표기를_유지하고_소유격만_뗀다():
    assert surfaces(tokenize("React's hooks", EN, lexicon=LEXICON)) == ["React", "hooks"]


def test_대문자_약어는_글자가_둘_이상이어야_한다():
    """`X1` 은 버전 꼴이고 약어가 아니다."""
    (token,) = tokenize("X1", EN, lexicon=LEXICON)
    assert token.kind == tk.VERSION


def test_코드_식별자_규칙을_끄면_쪼갠다():
    """패션 도메인 ([04 §8]). `next.config` 가 한 덩이로 남으면 잡음만 는다."""
    options = TokenizeOptions(code_identifiers=False)
    tokens = tokenize("next.config snake_case", EN, lexicon=LEXICON, options=options)

    assert [(t.surface, t.kind) for t in tokens] == [
        ("next", tk.WORD),
        ("config", tk.WORD),
        ("snake", tk.WORD),
        ("case", tk.WORD),
    ]


def test_en_문서에는_형태소_분석기를_태우지_않는다():
    """[04 §2] 영어 절 — 바꾸지 않은 것이 결정이다. 영문 글의 한글은 대개 고유명사고
    조사가 붙어 있을 이유가 없다."""
    assert surfaces(tokenize("컬렉션을", EN, lexicon=LEXICON)) == ["컬렉션을"]
    assert surfaces(ko("컬렉션을")) == ["컬렉션"]


# --- 혼합 문서 ------------------------------------------------------------------


def test_영문에_붙은_조사를_분석기가_가른다():
    tokens = tokenize("MCP는 Python으로", MIXED, lexicon=LEXICON)

    assert [(t.surface, t.kind) for t in tokens] == [("MCP", tk.ACRONYM), ("Python", tk.WORD)]
    assert boundaries(tokens) == ["MCP", "Python"]


def test_한글이_없는_표기는_영문_분류기가_종류를_정한다():
    """분석기는 `SL`·`SN` 까지만 안다 — 약어·버전·식별자 구분은 우리 몫이다."""
    tokens = tokenize("ES2023 API 발표", MIXED, lexicon=LEXICON)

    assert [(t.surface, t.kind) for t in tokens] == [
        ("ES2023", tk.VERSION),
        ("API", tk.ACRONYM),
        ("발표", tk.HANGUL),
    ]


# --- 경계 -----------------------------------------------------------------------


def test_구두점과_줄바꿈이_경계다():
    tokens = tokenize("how we build. useEffect hooks\nReact", EN, lexicon=LEXICON)

    assert boundaries(tokens) == ["build", "hooks", "React"]


def test_한국어도_줄바꿈이_경계다():
    """[03 §4] 가 문장 경계 정보로 줄바꿈 하나를 남긴 이유가 이것이다."""
    tokens = ko("가을 코트\n밀라노 컬렉션")

    assert boundaries(tokens) == ["코트", "컬렉션"]


def test_한_글자_영문은_경계다():
    """`F/W 런웨이` 에서 `W 런웨이` 라는 조각이 나오면 안 된다."""
    tokens = ko("2026 F/W 런웨이")

    assert surfaces(tokens) == ["2026", "런웨이"]
    assert tokens[0].boundary_after is True


def test_해시태그는_홀로_선다():
    tokens = tokenize("new #vibecoding trend", EN, lexicon=LEXICON)

    assert surfaces(tokens) == ["new", "#vibecoding", "trend"]
    assert boundaries(tokens) == ["new", "#vibecoding", "trend"]


def test_한국어_해시태그는_분석기가_태깅한다():
    """kiwipiepy 가 `W_HASHTAG` 를 직접 준다 — 우리 정규식이 하던 일이다
    (`morphology.HASHTAG_TAG`)."""
    tokens = ko("가을 #올가을트렌드 룩")

    assert [(t.surface, t.kind) for t in tokens][1] == ("#올가을트렌드", tk.HASHTAG)
    assert boundaries(tokens) == ["가을", "#올가을트렌드", "룩"]


@pytest.mark.parametrize("text", [None, "", "   ", "...", "\n\n"])
def test_빈_입력은_빈_목록(text):
    assert ko(text) == []
