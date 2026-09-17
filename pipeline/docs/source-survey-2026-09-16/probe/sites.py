# ruff: noqa — 2026-09-16 일회성 실측 기록. 실행한 그대로 보존한다.
"""측정 대상. feeds = 순서대로 시도할 피드 후보, discover = 피드 링크를 찾을 페이지(+골라낼 키워드).

added=True 는 조사 파일에 없고 같은 규칙으로 추가한 동류 매체다.
retail = 리테일러 에디토리얼 목록 페이지 (피드 대신 HTML 1장만 판정).
"""

S = []


def site(key, name, country, kind, feeds=(), discover=None, kw=None, added=False, retail=None, retail_pat=None, domain=None, src="survey"):
    S.append(dict(key=key, name=name, country=country, kind=kind, feeds=list(feeds), discover=discover, kw=kw,
                  added=added, retail=retail, retail_pat=retail_pat, domain=domain))


# ---- 유형 1 매거진
site("vogue_us", "Vogue US", "US", "magazine", ["https://www.vogue.com/feed/rss"])
site("harpersbazaar_us", "Harper's Bazaar US", "US", "magazine", ["https://www.harpersbazaar.com/rss/fashion.xml"])
site("elle_us", "ELLE US", "US", "magazine", ["https://www.elle.com/rss/all.xml"])
site("whowhatwear", "Who What Wear", "US", "magazine", ["https://www.whowhatwear.com/feeds.xml", "https://www.whowhatwear.com/rss"])
site("gq_us", "GQ US", "US", "magazine", ["https://www.gq.com/feed/rss"], added=True)
site("glamour_uk", "Glamour UK", "UK", "magazine", ["https://www.glamourmagazine.co.uk/feed/rss"])
site("marieclaire_uk", "Marie Claire UK", "UK", "magazine", ["https://www.marieclaire.co.uk/feeds/tag/fashion", "https://www.marieclaire.co.uk/feeds.xml"])
site("dazed", "Dazed", "UK", "magazine", ["https://www.dazeddigital.com/rss"])
site("vogue_uk", "Vogue UK", "UK", "magazine", ["https://www.vogue.co.uk/feed/rss"], added=True)
site("id", "i-D", "UK", "magazine", ["https://i-d.co/feed/"], discover="https://i-d.co/")
site("another", "AnOther (Substack)", "UK", "magazine", ["https://anothermag.substack.com/feed"])
site("032c", "032c", "DE", "magazine", ["https://032c.com/feed"], discover="https://032c.com/")
site("mensnonno", "MEN'S NON-NO", "JP", "magazine", ["https://www.mensnonno.jp/blog/feed/"])
site("fudge", "FUDGE", "JP", "magazine", ["https://fudge.jp/fashion/feed/"])
site("oggi", "Oggi", "JP", "magazine", ["https://oggi.jp/fashion/feed"])
site("houyhnhnm", "Houyhnhnm", "JP", "magazine", ["https://www.houyhnhnm.jp/feed"])
site("vogue_jp", "Vogue Japan", "JP", "magazine", ["https://www.vogue.co.jp/feed/rss"])
site("popeye", "POPEYE Web", "JP", "magazine", [], discover="https://popeyemagazine.jp/")
site("cancam", "CanCam", "JP", "magazine", ["https://cancam.jp/feed"], discover="https://cancam.jp/")
site("ginza", "GINZA", "JP", "magazine", [], discover="https://ginzamag.com/")
site("figaro_jp", "Madame Figaro JP", "JP", "magazine", [], discover="https://madamefigaro.jp/")
site("vogue_fr", "Vogue France", "FR", "magazine", ["https://www.vogue.fr/feed/rss"])
site("elle_fr", "ELLE.fr", "FR", "magazine", [], discover="https://www.elle.fr/")
site("madame_figaro", "Madame Figaro", "FR", "magazine", [], discover="https://madame.lefigaro.fr/")
site("lofficiel", "L'Officiel", "FR", "magazine", [], discover="https://www.lofficiel.com/")
site("numero", "Numéro", "FR", "magazine", [], discover="https://www.numero.com/fr")
site("vogue_it", "Vogue Italia", "IT", "magazine", ["https://www.vogue.it/feed/rss"])
site("grazia_it", "Grazia.it", "IT", "magazine", ["https://www.grazia.it/feed"], discover="https://www.grazia.it/")
site("iodonna", "Io Donna", "IT", "magazine", ["https://www.iodonna.it/feed/"], discover="https://www.iodonna.it/")
site("elle_it", "Elle Italia", "IT", "magazine", ["https://www.elle.com/it/rss/all.xml"])
site("vogue_cn", "Vogue China", "CN", "magazine", [], discover="https://www.vogue.com.cn/")
site("bazaar_cn", "时尚芭莎", "CN", "magazine", [], discover="https://www.bazaar.com.cn/")
site("elle_cn", "ELLE China", "CN", "magazine", [], discover="https://www.ellechina.com/")

# ---- 유형 2 업계지
for ed, c in (("us", "US"), ("uk", "UK"), ("fr", "FR"), ("it", "IT"), ("jp", "JP"), ("cn", "CN")):
    site(f"fashionnetwork_{ed}", f"FashionNetwork {ed}", c, "trade", [], discover=f"https://{ed}.fashionnetwork.com/rss/", kw="rss")
site("fashionunited", "FashionUnited", "NL/INTL", "trade", ["https://fashionunited.info/rss-news"])
site("wwd", "WWD", "US", "trade", ["https://wwd.com/feed/"])
site("bof", "Business of Fashion", "US/UK", "trade", ["https://www.businessoffashion.com/arc/outboundfeeds/rss/?outputType=xml"])
site("fashionista", "Fashionista", "US", "trade", ["https://fashionista.com/.rss/excerpt/"])
site("drapers", "Drapers", "UK", "trade", ["https://www.drapersonline.com/feed"])
site("theindustry", "TheIndustry.fashion", "UK", "trade", ["https://theindustry.fashion/feed/"])
site("fashionsnap", "Fashionsnap", "JP", "trade", ["https://www.fashionsnap.com/rss.xml"])
site("wwdjapan", "WWDJAPAN", "JP", "trade", ["https://www.wwdjapan.com/feed"], discover="https://www.wwdjapan.com/")
site("senken", "繊研新聞", "JP", "trade", [], discover="https://senken.co.jp/")
site("fashionpress", "Fashion Press", "JP", "trade", [], discover="https://www.fashion-press.net/")
site("journaldutextile", "Journal du Textile", "FR", "trade", [], discover="https://www.journaldutextile.com/")
site("pambianco", "Pambianco News", "IT", "trade", ["https://www.pambianconews.com/feed/"])
site("mffashion", "MF Fashion", "IT", "trade", [], discover="https://www.mffashion.com/")
site("luxe_co", "华丽志 Luxe.co", "CN", "trade", ["https://luxe.co/feed"], discover="https://luxe.co/")
site("jingdaily", "Jing Daily", "CN", "trade", ["https://jingdaily.com/feed/"], discover="https://jingdaily.com/")
site("ktnews", "한국섬유신문", "KR", "trade", ["https://www.ktnews.com/rss/allArticle.xml"])
site("itnk", "국제섬유신문", "KR", "trade", ["https://www.itnk.co.kr/rss/allArticle.xml"])
site("fashionbiz", "패션비즈", "KR", "trade", [], discover="https://fashionbiz.co.kr/")
site("apparelnews", "어패럴뉴스", "KR", "trade", [], discover="https://www.apparelnews.co.kr/")
site("fashioninsight", "패션인사이트", "KR", "trade", ["https://www.fashioninsight.co.kr/rss/allArticle.xml"], discover="https://www.fashioninsight.co.kr/")
site("highsnobiety", "Highsnobiety", "DE/INTL", "trade", ["https://www.highsnobiety.com/feeds/rss"])

# ---- 유형 4 보도자료 배포사 (패션 분류)
site("prnewswire", "PR Newswire Fashion", "US", "press", ["https://www.prnewswire.com/rss/consumer-products-retail-latest-news/fashion-list.rss"], discover="https://www.prnewswire.com/rss/", kw="fashion")
site("businesswire", "Business Wire Fashion", "US", "press", [], discover="https://www.businesswire.com/newsroom/industry/retail/fashion", kw="")
# 1차 실행에서 discover(rss/list)로 찾았으나 URL 공백 미인코딩으로 요청 전에 실패 → 인코딩한 피드만 재실행
site("globenewswire", "GlobeNewswire Clothing", "US", "press", ["https://www.globenewswire.com/AtomFeed/industry/3763-Clothing%2026%20Accessories/feedTitle/GlobeNewswire%20-%20Industry%20News%20on%20Clothing%20and%20Accessories"])
site("prtimes", "PR TIMES fashion", "JP", "press", [], discover="https://prtimes.jp/fashion/", kw="")
site("newswire_kr", "뉴스와이어 패션", "KR", "press", [], discover="https://www.newswire.co.kr/?md=A31", kw="패션")
site("prnasia", "美通社", "CN", "press", [], discover="https://www.prnasia.com/", kw="")

# ---- 유형 6 블로그 플랫폼 대표
site("substack_bbsp", "Blackbird Spyplane (Substack)", "US", "blog", ["https://www.blackbirdspyplane.com/feed"])
site("substack_opulent", "Opulent Tips (Substack)", "US", "blog", ["https://opulenttips.substack.com/feed"])
site("medium_tag", "Medium tag/fashion", "US", "blog", ["https://medium.com/feed/tag/fashion"])
site("ameba", "Ameba chiisai-fashion", "JP", "blog", ["https://rssblog.ameba.jp/chiisai-fashion/rss20.xml"])
site("hatena", "はてな akanaka-fashion", "JP", "blog", ["https://akanaka-fashion.hatenablog.com/rss"])
site("note_mb", "note MB(knowermag)", "JP", "blog", ["https://note.com/knowermag/rss"])
site("naver_blog", "네이버 블로그 wlsgkghgh", "KR", "blog", ["https://rss.blog.naver.com/wlsgkghgh.xml"])
site("brunch", "브런치 @@drZi", "KR", "blog", ["https://brunch.co.kr/rss/@@drZi"])

# ---- 리테일러 에디토리얼 (목록 1장)
site("ssense", "SSENSE Editorial", "CA", "retail", retail="https://www.ssense.com/en-us/editorial", retail_pat="/editorial/")
site("mrporter", "MR PORTER Journal", "UK", "retail", retail="https://www.mrporter.com/en-us/journal", retail_pat="/journal/")
site("end", "END. Features", "UK", "retail", retail="https://www.endclothing.com/us/features", retail_pat="/features/")
site("beams", "BEAMS blog", "JP", "retail", retail="https://www.beams.co.jp/blog/", retail_pat="/blog/")
site("musinsa", "무신사 매거진", "KR", "retail", retail="https://www.musinsa.com/content/list?contentCategoryCode=001001", retail_pat="/content/")
site("29cm", "29CM 콘텐츠", "KR", "retail", retail="https://www.29cm.co.kr/content", retail_pat="content")
site("wconcept", "W컨셉 콘텐츠", "KR", "retail", retail="https://www.wconcept.co.kr/", retail_pat="content|magazine|story")

SITES = S
