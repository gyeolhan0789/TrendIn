"""본문 HTML → 평문 (설계 문서 #5.3)."""

from trendin.common.collect.html_text import html_to_text, looks_like_html


def test_문단_경계가_빈_줄이_된다():
    assert html_to_text("<p>첫째</p><p>둘째</p>") == "첫째\n\n둘째"
    assert html_to_text("한 줄<br>다음 줄") == "한 줄\n\n다음 줄"


def test_버리는_태그는_안의_텍스트까지_사라진다():
    html = "<p>본문</p><script>alert(1)</script><style>p{}</style><svg><path/>안보임</svg>"
    assert html_to_text(html) == "본문"


def test_figcaption_은_본문이_아니다():
    """실측 214개 표본 12/12 가 Getty Images·@인스타핸들 같은 사진 크레딧이었다."""
    html = "<p>기사 문장</p><figure><img/><figcaption>Getty Images</figcaption></figure>"
    assert html_to_text(html) == "기사 문장"


def test_중첩된_버림_태그도_짝이_맞는다():
    assert html_to_text("<p>앞</p><svg><svg>안</svg></svg><p>뒤</p>") == "앞\n\n뒤"


def test_공백과_nbsp_는_한_칸으로_모인다():
    assert html_to_text("<p>가  \n 나</p>") == "가 나"


def test_빈_입력은_빈_문자열():
    assert html_to_text("") == ""
    assert html_to_text("<p></p><div>  </div>") == ""


def test_태그가_있으면_요약이_아니라_본문_사본으로_본다():
    assert looks_like_html("<p>본문</p>") is True
    assert looks_like_html("평문 요약이다") is False
    assert looks_like_html("") is False
