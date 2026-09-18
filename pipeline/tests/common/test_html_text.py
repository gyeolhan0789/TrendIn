"""본문 HTML → HTML 조각 (설계 문서 #5.3)."""

from trendin.common.collect.html_text import html_fragment, text_length


def test_마크업은_남긴다():
    assert (
        html_fragment("<p>첫째</p><p>둘째 <b>굵게</b></p>") == "<p>첫째</p><p>둘째 <b>굵게</b></p>"
    )
    assert html_fragment("한 줄<br>다음 줄<br/>끝") == "한 줄<br>다음 줄<br>끝"


def test_글자_속_꺾쇠와_앰퍼샌드는_이스케이프로_남는다():
    """Spark 가 태그를 벗긴 뒤에도 영화 제목이 남아야 한다 (#5.3, 2026-09-17 합의)."""
    assert html_fragment("<p>영화 &lt;문라이트(Moonlight)&gt;를 A &amp; B</p>") == (
        "<p>영화 &lt;문라이트(Moonlight)&gt;를 A &amp; B</p>"
    )


def test_평문도_조각이_된다():
    """ld+json·평문 요약처럼 태그가 없는 입력. 한글 앞 꺾쇠는 태그가 아니다."""
    assert html_fragment("평문 <문라이트> & 요약") == "평문 &lt;문라이트&gt; &amp; 요약"


def test_속성값은_따옴표째_이스케이프된다():
    assert html_fragment('<a href="/x?a=1&amp;b=&quot;2&quot;">링크</a>') == (
        '<a href="/x?a=1&amp;b=&quot;2&quot;">링크</a>'
    )


def test_버리는_태그는_안의_텍스트까지_사라진다():
    html = "<p>본문</p><script>alert(1)</script><style>p{}</style><svg><path/>안보임</svg>"
    assert html_fragment(html) == "<p>본문</p>"


def test_figcaption_은_본문이_아니다():
    """실측 214개 표본 12/12 가 Getty Images·@인스타핸들 같은 사진 크레딧이었다."""
    html = '<p>기사 문장</p><figure><img src="a.jpg"><figcaption>Getty Images</figcaption></figure>'
    assert html_fragment(html) == '<p>기사 문장</p><figure><img src="a.jpg"></figure>'


def test_중첩된_버림_태그도_짝이_맞는다():
    assert html_fragment("<p>앞</p><svg><svg>안</svg></svg><p>뒤</p>") == "<p>앞</p><p>뒤</p>"


def test_주석과_선언은_싣지_않는다():
    assert html_fragment("<!DOCTYPE html><!-- 광고 --><p>본문</p>") == "<p>본문</p>"


def test_구간_안쪽만_적고_구간을_연_요소는_뺀다():
    html = (
        '<nav>메뉴</nav><div class="atc_body_cont"><div><p>첫</p></div>'
        '<div class="atc_mask_login">마스크<div>안</div></div><p>둘</p></div><p>밖</p>'
    )
    assert (
        html_fragment(
            html, within_class="atc_body_cont", drop_classes=frozenset({"atc_mask_login"})
        )
        == "<div><p>첫</p></div><p>둘</p>"
    )


def test_글자가_없으면_빈_문자열():
    assert html_fragment("") == ""
    assert html_fragment("<p></p><div>  </div>") == ""
    assert html_fragment('<figure><img src="a.jpg"></figure>') == ""


def test_글자_수는_공백을_세지_않는다():
    assert text_length("<p>가 나</p>\n<p>다&amp;</p>") == 4
