# 패션 글 소스 확장 조사 — 어떤 소스를 어떤 경로로

- 조사일: 2026-09-16. 대상 사이트는 직접 열지 않았다. 검색 결과, 공식 API·개발자 문서, 제3자 목록(Feedspot 등), GitHub 이슈·기술 블로그만 썼다.
- 근거 등급: **②** 출처 있음(URL 적음) / **③** 추정. ① 실측은 없다(대상 사이트를 치지 않았으므로).
- Feedspot 에 피드 URL 이 올라 있다는 건 "제3자가 그 주소를 목록에 올렸다"는 사실(②)이다. 지금 살아 있는지, 전문인지 요약인지는 따로 재야 한다(③).
- "우리 수집기 가능성" 칸: **가능** = stdlib HTTP + html.parser/XML 로 된다 / **조건부** = 키·승인·쿠키·유료 중 하나가 필요 / **어려움** = JS 렌더링·요청 서명·강한 봇 차단·로그인이 걸린다.
- 텍스트 칸: **본문** / **제목·캡션** / **이미지뿐**.

---

## 1. 유형별 요약 표

### 1.1 유형 1 — 패션 매거진 (해외판·독립지)

| 국가 | 소스 | 접근 경로 | 텍스트 | 기술적 장벽 | 언어 | 가능성 | 근거 |
|---|---|---|---|---|---|---|---|
| 미국 | Vogue US | RSS `vogue.com/feed/rss` | 본문 기사. 피드는 요약만일 가능성 ③ | 없음(알려진 것) | en | 가능 | ② https://rss.feedspot.com/fashion_rss_feeds/ |
| 미국 | Harper's Bazaar US · ELLE US (Hearst) | RSS `harpersbazaar.com/rss/fashion.xml`, `elle.com/rss/all.xml` | 본문 기사 | 없음(알려진 것) | en | 가능 | ② 같은 목록 |
| 미국 | Who What Wear | RSS `whowhatwear.com/feeds.xml` | 본문 | — | en | 가능 | ② https://rss.feedspot.com/fashion_news_rss_feeds/ |
| 영국 | Glamour UK · Marie Claire UK | RSS `glamourmagazine.co.uk/feed/rss`, `marieclaire.co.uk/feeds/tag/fashion` | 본문 | — | en | 가능 | ② https://rss.feedspot.com/uk_fashion_rss_feeds/ |
| 영국 | Dazed | RSS `dazeddigital.com/rss` | 본문 | — | en | 가능 | ② 검색 결과 https://www.dazeddigital.com/rss |
| 영국 | i-D · AnOther · 032c | 네이티브 피드 못 찾음. AnOther 는 Substack 도 운영 | 본문 | 목록 HTML 을 읽어야 함 | en | 반반 ③ | ② https://anothermag.substack.com/ |
| 일본 | MEN'S NON-NO · FUDGE · Oggi · Houyhnhnm | RSS `mensnonno.jp/blog/feed/`, `fudge.jp/fashion/feed/`, `oggi.jp/fashion/feed`, `houyhnhnm.jp/feed` (WordPress 꼴 ③) | 본문 | — | ja | 가능 | ② https://rss.feedspot.com/japanese_fashion_rss_feeds/ |
| 일본 | Vogue Japan · Popeye · CanCam · GINZA · Madame Figaro JP | Feedspot 에 "RSS 생성 필요"로 올라 있음 → 네이티브 피드 없음 추정 | 본문 | 목록 HTML. JS 여부 모름 | ja | 반반 ③ | ② 같은 목록 |
| 프랑스 | Vogue France | RSS `vogue.fr/feed/rss` (Condé Nast 공통 경로) | 본문 | — | fr | 가능 | ② 검색 결과(Feedspot French RSS) |
| 프랑스 | ELLE.fr · Madame Figaro · L'Officiel · Numéro | 피드 확인 못 함. 르피가로 본지는 `lefigaro.fr/rss/figaro_{섹션}.xml` 규칙 | 본문 | — | fr | 반반 ③ | ② https://lolobobo.fr/2024/11/25/abonner-flux-rss-thematique-quotidien-francais/ |
| 이탈리아 | Vogue Italia | Feedspot 에 피드 대신 페이지 URL(`vogue.it/moda`)만 있음. Condé Nast 공통 경로 `/feed/rss` 일 가능성 ③ | 본문 | — | it | 반반 ③ | ② https://rss.feedspot.com/italian_fashion_rss_feeds/ |
| 이탈리아 | Grazia.it · Io Donna · Elle Italia | 확인 못 함 | 본문 | — | it | 모름 | — |
| 중국 | Vogue China(vogue.com.cn) · 时尚芭莎 · ELLE China | 피드 정보 없음. 유통 주력이 위챗 공식계정·샤오홍슈라는 것은 추정 | 본문 | 위챗 쪽은 #1.5 참고 | zh | 어려움 ③ | ② https://en.wikipedia.org/wiki/Vogue_China (도메인만) |

### 1.2 유형 2 — 패션 업계 전문지

| 국가 | 소스 | 접근 경로 | 텍스트 | 기술적 장벽 | 언어 | 가능성 | 근거 |
|---|---|---|---|---|---|---|---|
| 다국 | **FashionNetwork** (미·영·프·이·독·스페인·중·일·인도 등 15판) | 판마다 `/rss/` 페이지, 분야별 피드(Retail·Business·Industry 등) | 본문 기사(피드는 요약일 수 있음 ③) | 알려진 것 없음 | en/fr/it/ja/zh… | 가능 | ② https://us.fashionnetwork.com/rss/ · https://ww.fashionnetwork.com/rss/ · 판 목록 https://us.fashionnetwork.com/about/ |
| 다국 | FashionUnited | RSS `fashionunited.info/rss-news` | 본문 | — | en 외 ③ | 가능 | ② https://rss.feedspot.com/fashion_news_rss_feeds/ |
| 미국 | WWD | RSS 목록 페이지 있음. `wwd.com/feed/`, `wwd.com/business-news/feed/`, `wwd.com/custom-feed/recent-stories/`. WordPress VIP | 본문. 유료 기사 섞임 ③ | 피드는 "헤드라인 개인 열람용"이라 명시(약관 문구라 판정 제외) | en | 가능(헤드라인), 본문은 반반 | ② https://wwd.com/rss-feeds/ (검색 스니펫) · https://en.wikipedia.org/wiki/Women%27s_Wear_Daily |
| 미국·영국 | Business of Fashion | Arc XP 피드 `businessoffashion.com/arc/outboundfeeds/rss/?outputType=xml` | 제목·요약. 본문 대부분 **페이월**(월 무료 1건 안내) | 페이월 | en | 조건부 | ② https://rss.feedspot.com/fashion_industry_rss_feeds/ · https://pages.businessoffashion.com/daily-digest-signup/ |
| 미국 | Fashionista | `fashionista.com/.rss/excerpt/` — 경로 이름부터 **요약 피드** | 제목·요약 | — | en | 가능(요약만) | ② 같은 목록 |
| 영국 | Drapers · TheIndustry.fashion | RSS `drapersonline.com/feed`, `theindustry.fashion/feed/` | 본문. Drapers 는 유료 구독지 ③ | Drapers 페이월 ③ | en | 가능 / 반반 | ② https://rss.feedspot.com/fashion_industry_rss_feeds/ |
| 일본 | Fashionsnap | RSS `fashionsnap.com/rss.xml` | 본문 | — | ja | 가능 | ② https://rss.feedspot.com/japanese_fashion_rss_feeds/ |
| 일본 | WWDJAPAN | 피드 확인 못 함 | 본문. **유료 회원 한정 기사 목록이 따로 있음** | 페이월(일부) | ja | 반반 | ② https://www.wwdjapan.com/subscriptions/paywall |
| 일본 | 繊研新聞 · Fashion Press | 확인 못 함. 繊研은 PR TIMES 보도자료 면을 운영 | 본문. 繊研 전자판 유료 ③ | 페이월 ③ | ja | 반반 ③ | ② https://senken.co.jp/prtimes |
| 프랑스 | Journal du Textile | 사이트는 호수 요약·기사 발췌만, 전문은 구독 | 제목·발췌 | 페이월 | fr | 조건부 | ② https://www.journaldutextile.com/ (검색 스니펫) |
| 이탈리아 | Pambianco News | 피드 확인 못 함. URL 꼴(`/tag/…`)이 WordPress 같음 ③ | 본문 | — | it | 반반 ③ | ② https://www.pambianconews.com/news/ |
| 이탈리아 | MF Fashion | 앱·디지털 신문 구독 판매 | 본문 | 페이월 ③ | it | 조건부 ③ | ② https://www.mffashion.com/ (검색 스니펫) |
| 중국 | 华丽志 Luxe.co | 사이트 + 앱 + 위챗. URL 꼴(`/post/{숫자}`, `/tag/…`)이 WordPress 같음 ③ | 본문 | — | zh | 반반 ③ | ② https://luxe.co/about |
| 중국 | FashionNetwork 中国 · Jing Daily(영문) | FashionNetwork 판 공통 경로 / Jing Daily 는 확인 못 함 | 본문 | — | zh/en | 가능 / 모름 | ② https://cn.fashionnetwork.com/tags/news/vogue.html |
| 한국 | 한국섬유신문(ktnews) · 국제섬유신문(itnk) | `articleList.html` URL 꼴 → 국내 인터넷신문 CMS 공통 `/rss/allArticle.xml` 경로일 가능성 | 본문 | — | ko | 가능 ③ | ② https://www.itnk.co.kr/news/articleList.html?view_type=sm · 같은 경로 사례 https://junpyopark.github.io/rss_parse/ |
| 한국 | 패션비즈 · 어패럴뉴스 · 패션인사이트 | 피드 확인 못 함. 패션비즈에 "프리미엄 리포트" 있음 | 본문 / 일부 유료 ③ | 페이월(일부) ③ | ko | 반반 ③ | ② https://fashionbiz.co.kr/ (검색 스니펫) |

### 1.3 유형 3 — 편집숍·리테일러 에디토리얼

| 국가 | 소스 | 접근 경로 | 텍스트 | 기술적 장벽 | 언어 | 가능성 | 근거 |
|---|---|---|---|---|---|---|---|
| 캐나다/글로벌 | SSENSE Editorial | 네이티브 피드 못 찾음. 목록 HTML | 본문(긴 에세이) | 대형 리테일러라 봇 차단 서비스(Akamai 등) 가능성 ③ | en | 반반 ③ | ② 경로 존재만 https://www.ssense.com/en-us/editorial/fashion/back-to-basics |
| 영국 | MR PORTER The Journal | 2013년에 RSS 개설 소식. 지금 살아 있는지 모름 | 본문 | 대형 리테일러(YNAP) 봇 차단 ③ | en | 반반 ③ | ② https://thisfits.me/post/54701249218/the-mr-porter-journal-now-has-an-rss-feed |
| 영국 | END. Features | 피드 못 찾음 | 본문 | ③ | en | 반반 ③ | ② https://www.endclothing.com/us/features |
| 독일/글로벌 | Highsnobiety | RSS `highsnobiety.com/feeds/rss`, 분야별 피드 | 본문 | — | en | 가능 | ② https://rss.feedspot.com/fashion_rss_feeds/ |
| 일본 | BEAMS 블로그 · ZOZOTOWN/WEAR | BEAMS 는 Feedspot 에 "RSS 생성 필요". WEAR 는 비공식 스크래퍼만 | BEAMS: 제목·캡션 위주 ③ / WEAR: **사진 + 태그·짧은 캡션** | WEAR JS ③ | ja | 반반 / 어려움 ③ | ② https://rss.feedspot.com/japanese_fashion_rss_feeds/ · https://apify.com/jungle_synthesizer/wear-zozo-fashion-coordinate-outfit-scraper |
| 한국 | 무신사 콘텐츠(매거진) | `musinsa.com/content/list?...` 목록. 리뷰 페이지는 SPA 가상 스크롤로 Puppeteer 가 필요했다는 사례 | 본문 + 상품 사진 | 콘텐츠 페이지 JS 여부 모름. 리뷰 쪽은 JS 필수 사례 있음 | ko | 반반 ③ | ② https://www.musinsa.com/content/list?contentCategoryCode=001001 · https://velog.io/@developer_beaver/%EB%AC%B4%EC%8B%A0%EC%82%AC-%EB%A6%AC%EB%B7%B0-%EB%8D%B0%EC%9D%B4%ED%84%B0-%ED%81%AC%EB%A1%A4%EB%A7%81%ED%95%98%EA%B8%B0Musinsa-Web-Site-review-Crawling |
| 한국 | 29CM(PT·브랜드 코멘터리 등) · W컨셉 | 확인 못 함. 앱 중심 커머스라 JS 렌더링 가능성 높음 ③ | 본문 + 사진 | JS ③ | ko | 어려움 ③ | ② 콘텐츠 종류만 https://blog.martinee.io/post/fashion-platforms-growthmarketing-musinsa-29cm-wconcept |
| 프랑스·이탈리아·중국 | Galeries Lafayette, LuisaViaRoma, 得物 등 | 확인 못 함 | — | — | — | 모름 | — |

### 1.4 유형 4 — 브랜드 뉴스룸·보도자료 배포

| 국가 | 소스 | 접근 경로 | 텍스트 | 기술적 장벽 | 언어 | 가능성 | 근거 |
|---|---|---|---|---|---|---|---|
| 미국(+APAC) | PR Newswire | RSS 목록 페이지(본판·APAC판). 업종 목록에 **Fashion** 이 따로 있음 | 보도자료 본문 | — | en(+ja/zh 판 ③) | 가능 | ② https://www.prnewswire.com/rss/ · https://www.prnewswire.com/apac/rss/ · https://www.prnewswire.com/news-releases/consumer-products-retail-latest-news/fashion-list/ |
| 미국 | Business Wire | 업종 뉴스룸 `newsroom/industry/retail/fashion`, RSS/Atom 제공 | 본문 | — | en(+fr 등 ③) | 가능 | ② https://www.businesswire.com/newsroom/industry/retail/fashion |
| 미국 | GlobeNewswire | RSS 목록 페이지. LVMH 보도자료도 올라옴 | 본문 | — | en/fr ③ | 가능 | ② https://www.globenewswire.com/rss/list · https://www.globenewswire.com/search/organization/LVMH |
| 일본 | PR TIMES | 업종 카테고리 `prtimes.jp/fashion/`. 카테고리 RSS 존재 여부는 스니펫이 불분명 | 본문 | — | ja | 가능 ③ | ② https://prtimes.jp/fashion/ |
| 한국 | 뉴스와이어 | 180개 분야 RSS | 본문 | — | ko | 가능 | ② https://www.newswire.co.kr/?md=A31 |
| 중국 | 美通社(PR Newswire Asia) | 확인 못 함 | 본문 | — | zh | 반반 ③ | — |
| 프랑스 | LVMH · Kering 프레스 | 공식 프레스 페이지. RSS 여부 모름. 배포는 PR Newswire·GlobeNewswire 로도 | 본문(실적·인사 위주) | — | en/fr | 배포사 경유 가능 | ② https://www.lvmh.com/en/press · https://www.prnewswire.com/news/lvmh/ |
| 미국 | Nike | IR 사이트 RSS 제공, 뉴스룸 `news.nike.com` | 본문 | — | en | 가능(IR) | ② https://investors.nike.com/investors/resources/investor-alerts/rss-feeds/default.aspx |
| 한국 | 무신사 뉴스룸 | `newsroom.musinsa.com/news/press` | 본문 | RSS 여부 모름 | ko | 반반 ③ | ② https://newsroom.musinsa.com/news/press |

### 1.5 유형 5 — 커뮤니티

| 국가 | 소스 | 접근 경로 | 텍스트 | 기술적 장벽 | 언어 | 가능성 | 근거 |
|---|---|---|---|---|---|---|---|
| 미국·영국 | Reddit (r/malefashionadvice, r/femalefashionadvice, r/streetwear 등) | ① 공식 Data API: 2025-11 Responsible Builder Policy 뒤로 **모든 신규 앱이 사전 승인 필요**(개인 프로젝트 포함). 무료 등급 OAuth 분당 100회, 상업 $0.24/1천 호출. ② `.rss`: 아직 대체로 되지만 **간헐적 403**, 브라우저 UA 로 풀린 사례 | 본문(셀프 포스트) + 사진 글은 제목만 | API 승인 / RSS 403 | en | 조건부(API) · 반반(RSS) | ② https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy · https://octolens.com/blog/reddit-api-pricing · https://github.com/FreshRSS/FreshRSS/issues/8189 · https://github.com/RSS-Bridge/rss-bridge/issues/4067 |
| 미국 | Styleforum · The Fashion Spot 포럼 | XenForo 라면 포럼별 `index.rss`. tFS 는 URL 꼴이 XenForo(`/threads/…`) | 본문 | — | en | 가능 ③ | ② XenForo RSS 규칙 https://xenforo.com/community/threads/how-to-get-rss-feed.164535/ · tFS URL https://forums.thefashionspot.com/threads/another-magazine-s-s-2025.417321/ |
| 글로벌 | Superfuture Supertalk | Invision 계열 URL 꼴(`/forum/28-…`) ③. **2026년 구독제 도입 중** | 본문 | 구독제가 열람을 막는지 모름 | en | 반반 | ② https://supertalk.superfuture.com/ (검색 스니펫) |
| 한국 | 디시인사이드 패션 갤러리 | 공식 RSS 확인 못 함. 비공식 RSS 서비스(dc-feed)가 있음 | 본문(짧음) | — | ko | 반반 ③ | ② https://m.dcinside.com/board/programming/230883 |
| 한국 | 더쿠 | 과거 디도스로 **자동 크롤링을 사이트가 막은 적 있음** | 본문 | 봇 차단 | ko | 어려움 ③ | ② https://theqoo.net/vincenzo/2049415747 |
| 한국 | 네이버 카페(패션 카페) | 공식 API 없음. 카페 가입·등급이 있어야 글을 봄. iframe 구조 | 본문 | **로그인·가입 필수** | ko | 어려움 | ② https://yahwang.github.io/posts/4 |
| 한국 | 에펨코리아·인스티즈 등 | 확인 못 함. 에펨코리아는 Cloudflare 이슈 글이 있음 | 본문 | Cloudflare ③ | ko | 모름 | ② https://m.fmkorea.com/best/9772035244/9772042178 (정황만) |
| 일본 | 5ch ファッション板 | 스레드 `dat` 경로. 전용 브라우저 규제 이력 | 본문 | Cloudflare 여부 ③ | ja | 반반 ③ | ② https://info.5ch.net/index.php/Monazilla/develop |
| 일본 | WEAR | #1.3 참고 | 사진 + 태그 | JS ③ | ja | 어려움 ③ | ② 위 |
| 중국 | 샤오홍슈(小红书) | 공개 API 없음. 웹 API 가 `x-s`/`x-s-common`/`x-t` **요청 서명**을 요구하고 서명 방식이 월 단위로 바뀜. 일부 콘텐츠 로그인 쿠키 필요 | 노트 본문(짧은 글) + 사진 | 서명·로그인·JS | zh | 어려움 | ② https://dev.to/sami_8858131362756585e4f4/how-to-scrape-rednote-xiaohongshu-with-python-in-2026-the-authsigning-problem-and-how-to-3f9e |
| 중국 | 웨이보 | 공식 Search API 는 **파트너 개발자 전용**. 비공식 경로는 쿠키 필요 | 짧은 본문 | 파트너 승인 / 로그인 쿠키 | zh | 어려움 | ② https://open.weibo.com/wiki/Search_API · RSSHub 설정 https://docs.rsshub.app/deploy/config |
| 중국 | 豆瓣 그룹 | 쿠키 없이 요청하면 **보안 검증 페이지로 리다이렉트** | 본문 | 로그인 쿠키·캡차 | zh | 어려움 | ② https://github.com/DIYgod/RSSHub/pull/23277 |
| 프랑스·이탈리아 | 전용 패션 커뮤니티 | 찾지 못함. Reddit 국가별 서브레딧이 대안일 것 | — | — | fr/it | 모름 | — |

### 1.6 유형 6 — 블로그·뉴스레터

| 국가 | 플랫폼 | 접근 경로 | 텍스트 | 기술적 장벽 | 언어 | 가능성 | 근거 |
|---|---|---|---|---|---|---|---|
| 글로벌 | Substack | 발행물마다 `/feed`. 무료 글은 전문, **유료 글은 미리보기만** | 본문 | 유료 글 페이월. 발견용 검색 엔드포인트는 익명 호출에 빈 결과 | en 외 | 가능 | ② https://www.wprssaggregator.com/substack-rss-feed/ · 분야 랭킹 https://substack.com/top/fashionandbeauty |
| 글로벌 | Medium | `medium.com/feed/tag/{태그}`, 사람·발행물 피드. 멤버 전용 글은 짧은 미리보기 | 본문 | 멤버 전용 페이월 | en | 가능 | ② https://finder.wprssaggregator.com/rss-feeds/platform/medium · https://hlung.medium.com/how-to-get-rss-feed-url-for-your-medium-blog-72cee1b978a |
| 글로벌 | Ghost | `/rss/`, `/tag/{slug}/rss/`, `/author/{slug}/rss/`. 기본 전문 | 본문 | — | — | 가능 | ② https://finder.wprssaggregator.com/rss-feeds/platform/ghost |
| 글로벌 | WordPress · Blogger · Squarespace · Shopify 블로그 | `/feed`, `/category/x/feed/` · `/feeds/posts/default?alt=rss` · `?format=rss` · `/blogs/x.atom` | 본문(설정 따라 요약) | — | 전 언어 | 가능 | ② Feedspot 목록의 피드 URL 꼴들(https://rss.feedspot.com/french_fashion_rss_feeds/ 등) |
| 일본 | note.com | `note.com/{id}/rss`, 매거진 `/m/{id}/rss`. **전문 RSS 는 note pro 전용**, 해시태그 필터도 pro | 일반 계정은 요약 ③ | — | ja | 가능(요약) | ② https://note.com/koukichi_t/n/n15a5148cbe86 · https://www.help-note.com/hc/ja/articles/900001001246 (검색 스니펫) |
| 일본 | Ameba 블로그 | `rssblog.ameba.jp/{id}/rss20.xml` — RSS 2.0 은 전문, 1.0 은 발췌 | 본문 | — | ja | 가능 | ② https://ameblo.jp/staff/entry-12865036798.html · https://mono96.jp/blog-way/40796/ |
| 일본 | はてなブログ | `/rss`(RSS2), `/feed`(Atom). 기본 전문, 작성자가 요약으로 바꿀 수 있음 | 본문 | — | ja | 가능 | ② https://computerlife.hateblo.jp/entry/hateblo-rssfeed-url |
| 한국 | 네이버 블로그 | 블로그마다 `rss.blog.naver.com/{id}.xml`. 발견은 네이버 검색 API(블로그) — 하루 25,000회, 한 번 100건, start 최대 1000, 필드는 title·link·description(요약)·bloggername·postdate | RSS: 요약인지 전문인지 확인 못 함 ③ / 검색 API: 요약만 | 검색 API 는 키 필요(무료) | ko | 가능(RSS) · 조건부(발견) | ② https://wikidocs.net/48293 · https://choonghyunryu.github.io/posts/2022-03-01-open-api/ · https://velog.io/@gyu_p/API-%ED%99%9C%EC%9A%A9%ED%95%98%EA%B8%B0-%EB%84%A4%EC%9D%B4%EB%B2%84 |
| 한국 | 티스토리 | `/rss`, 건수 50까지 설정. **Open API 는 2024-02 종료** | 본문(설정 따라) | — | ko | 가능 | ② https://tistory.github.io/document-tistory-apis/ · https://blog.iolate.kr/171 |
| 한국 | 브런치 | 공식 RSS 없음. 페이지 소스에 `brunch.co.kr/rss/@@{id}` 가 숨어 있다는 사례, 외부 변환 서비스 | 본문 ③ | 비공식 | ko | 반반 | ② https://brunch.co.kr/@second-space/14 · https://brunch-rss.co.kr/ |
| 중국 | 위챗 공식계정 | 搜狗微信 검색은 계정당 **최근 10건만**. 과거 글은 자기 공식계정 로그인 뒤 인용 검색 방식, 많이 모으면 인증 걸림 | 본문 | 로그인·캡차 | zh | 어려움 | ② https://www.bazhuayu.com/helpcenter/docs/wei-xin-gong-zhong-hao-wen-zhang-cai-ji-fan-pa-jiao-yan-zhong · https://wechatsogou.readthedocs.io/zh-cn/latest/ |
| 중국 | 知乎 专栏 | API 호출에 `x-zse-96` 서명 필요 | 본문 | 요청 서명 | zh | 어려움 | ② https://www.cnblogs.com/tnanko/p/18164834 |
| 프랑스·이탈리아 | 개인 패션 블로그 다수 | 대부분 WordPress·Blogger 피드(Feedspot 프랑스 29곳, 이탈리아 49곳 목록) | 본문 | — | fr/it | 가능 | ② https://rss.feedspot.com/french_fashion_rss_feeds/ · https://rss.feedspot.com/italian_fashion_rss_feeds/ |

### 1.7 유형 7 — 영상 자막

| 국가 | 소스 | 접근 경로 | 텍스트 | 기술적 장벽 | 언어 | 가능성 | 근거 |
|---|---|---|---|---|---|---|---|
| 전체 | YouTube 공식 API — 자막 | `captions.download` 는 **영상 편집 권한이 있어야** 한다(=남의 영상 자막은 못 받음). `captions.list` 50 unit | 자막 없음(남의 영상) | OAuth + 소유권 | — | **불가** | ② https://developers.google.com/youtube/v3/docs/captions/download · https://developers.google.com/youtube/v3/determine_quota_cost |
| 전체 | YouTube 공식 API — 메타데이터 | `videos.list`(1 unit: 제목·설명), `commentThreads.list`(1 unit: 댓글), `search.list` 하루 100회. 기본 10,000 unit/일. API 키만 필요 | 제목·설명·댓글 텍스트 | 키(무료) | 전 언어 | 조건부(키) | ② https://developers.google.com/youtube/v3/determine_quota_cost |
| 전체 | YouTube 채널 RSS | `youtube.com/feeds/videos.xml?channel_id=UC…` 키 불필요 | 제목·설명 ③ | — | — | 가능 | ② https://guissmo.com/blog/youtube-channels-have-rss-feeds/ |
| 전체 | 비공식 자막(youtube-transcript-api) | 내부 엔드포인트 역공학. **클라우드 IP 대역을 YouTube 가 막음**, PoToken 등장 | 자막 전문 | IP 차단, 무보증 | — | 어려움 | ② https://github.com/jdepoix/youtube-transcript-api · https://github.com/hxckya/youtube-transcript-ip-blocked-guide |
| 중국 | Bilibili 자막 | 2025년부터 **자막 목록이 로그인 상태에서만** 보임. SESSDATA 쿠키 + WBI 서명 | 자막(AI 자막 포함) | 로그인·서명 | zh | 어려움 | ② https://github.com/the1812/Bilibili-Evolved/discussions/4795 · RSSHub 설정 https://docs.rsshub.app/deploy/config |
| 전체 | TikTok 음성 텍스트 | Research API 의 `voice_to_text` 필드(채워진 비율 약 1/5). 자격은 #1.8 | 전사 텍스트 | 연구자 자격 | — | 불가(우리 자격) | ② https://kinit.sk/when-research-apis-close-the-door-when-you-finally-get-it-it-is-not-what-you-have-asked-for/ |
| 일본 | niconico · 한국 네이버TV 등 | 확인 못 함 | — | — | — | 모름 | — |

### 1.8 유형 8 — SNS

| 소스 | 접근 경로 | 텍스트 | 기술적 장벽 | 가능성 | 근거 |
|---|---|---|---|---|---|
| Instagram | Graph API Hashtag Search. **비즈니스/크리에이터 계정 + "Instagram Public Content Access" 기능 승인** 필요. 계정당 **7일에 서로 다른 해시태그 30개**. `recent_media` 에서 `caption` 필드 요청 가능. 공개 콘텐츠 검색은 이것뿐 | 캡션(텍스트) + 사진 | 앱 리뷰·계정 조건·해시태그 한도 | 조건부 | ② https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search/ · https://developers.facebook.com/docs/instagram-api/reference/hashtag/recent-media |
| Threads | Keyword Search API. `threads_keyword_search` **앱 리뷰 승인 전에는 내 글만** 검색. 사용자당 24시간 2,200쿼리, 한 번 최대 100건, TEXT 필터 있음 | 본문(짧은 글) | 앱 리뷰 | 조건부 | ② https://developers.facebook.com/docs/threads/keyword-search/ |
| TikTok | Research API: **미국·EEA·영국·캐나다·스위스 학술기관**, EU 비영리 등만. 비상업. 하루 1,000요청 | 설명·해시태그·일부 전사 | **한국 학생 프로젝트는 자격 없음** | 불가 | ② https://developers.tiktok.com/products/research-api · https://www.xpoz.ai/blog/guides/tiktok-research-api-limits-access-and-alternatives/ |
| X | 신규는 사용량 과금만. 글 읽기 **$0.005/건**, 월 300만 건 상한, 크레딧 선불. 무료 등급 사실상 없음 | 본문(짧은 글) | 유료 | 조건부(유료) | ② https://docs.x.com/x-api/getting-started/pricing · https://postproxy.dev/blog/x-api-pricing-2026/ |
| Pinterest | API v5. Trial 앱 하루 1,000요청. 남의 핀 검색 `GET /v5/search/partner/pins` 은 Trial 승인 + 베타 접근 필요할 수 있음. 대부분의 API 데이터 캐싱 금지 규칙 | 핀 제목·설명 + **이미지 중심** | 승인·베타 | 어려움 | ② https://developers.pinterest.com/docs/getting-started/access-tiers/ · https://community.pinterest.biz/t/trial-access-and-beta-access-for-get-v5-search-partner-pins/48612 |
| (참고) Bluesky | 공개 AppView `public.api.bsky.app` 의 GET 은 인증 없이 호출 가능, Jetstream 무인증 | 본문 | 없음 | 가능 | ② https://docs.bsky.app/docs/advanced-guides/api-directory · https://docs.bsky.app/blog/jetstream |
| (중국) 웨이보·샤오홍슈·抖音 | #1.5 참고. 抖音 개방 플랫폼은 게시·자기 계정 기능 중심 ③ | 짧은 본문 / 영상 | 서명·로그인·파트너 | 어려움 | ② #1.5 |

### 1.9 유형 9 — 링크 모음·데이터셋

| 소스 | 주는 것 | 국가·언어 | 비용·한도 | 기술적 장벽 | 가능성 | 근거 |
|---|---|---|---|---|---|---|
| **GDELT DOC 2.0 API** | **URL + 메타데이터만**: url, url_mobile, title, seendate, socialimage, domain, language, sourcecountry. 본문 없음. 전문 검색은 GDELT 내부에서 기계번역 영어 본문에 대해 돈다 | 65개 언어를 영어로 번역해 검색. `sourcecountry:`, `sourcelang:`, `domain:`, `domainis:`, `theme:` | 무료, 키 없음. **요청 5초당 1회**(어기면 IP 단위 차단이 더 길게). 한 번 최대 250건. **최근 3개월 롤링 창**. 15분 단위 | 없음 | 가능 | ② https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ · https://github.com/alex9smith/gdelt-doc-api · https://github.com/alex9smith/gdelt-doc-api/issues/22 · https://blog.gdeltproject.org/gdelt-translingual-translating-the-planet/ |
| GDELT GKG 2.0 원시 파일 | 15분마다 CSV. 문서 URL + 테마·인물·조직 | 위와 같음 | 무료(BigQuery 는 과금) | 파일이 큼 | 가능 | ② https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/ |
| **CC-NEWS** (Common Crawl) | **WARC 원문 HTML** — 본문 추출은 우리가 한다 | 언어 제한 없음 | 무료. S3/HTTPS. 매일 WARC 공개. 2016 시작 당시 하루 약 5만 기사·압축 1GB. **URL 인덱스 없음**(CC-MAIN 컬럼 인덱스는 CC-NEWS 미포함) → 파일을 통째로 훑어야 함 | 인덱스 없음, 용량 | 가능(무겁다) | ② https://data.commoncrawl.org/crawl-data/CC-NEWS/index.html · https://groups.google.com/g/common-crawl/c/sKcq7CwmoE4 · https://groups.google.com/g/common-crawl/c/eQC0nLVqmQs |
| Google News RSS | 제목·출처·날짜. 링크는 **news.google.com 인코딩 리다이렉트**(2024년 인코딩 변경 뒤 원 URL 복원에 내부 `batchexecute` 호출 필요). 설명은 자주 비어 있음 | `hl`/`gl`/`ceid` 로 국가판. `site:`, `when:`, `after:`/`before:`, `intitle:` | 무료, 키 없음. **피드당 최대 약 100건, 페이지 넘김 없음** → 날짜로 잘라 반복. 공식 API 아님, 무보증. 중간값 기사 나이 약 6.6일이라는 측정 | URL 복원이 비공식 | 가능(URL 복원은 반반) | ② https://www.newscatcherapi.com/blog-posts/google-news-rss-search-parameters-the-missing-documentaiton · https://cloro.dev/blog/google-news-rss/ · https://github.com/SSujitX/google-news-url-decoder |
| NewsAPI.org | 메타데이터 + 짧은 스니펫(모든 요금제) | 다국 | 개발자 플랜 하루 100요청, **약 24시간 지연**, 약 1개월 과거, **개발·테스트 전용**(운영 금지) | 키 | 조건부 | ② https://newsapi.org/terms · https://apicostcalc.com/newsapi.html |
| GNews | 메타데이터 + 잘린 본문. 전문은 유료 `expand=content` | 다국 | 무료 하루 100요청, 요청당 10건, 12시간 지연, 30일 과거, 비상업. 유료 €49.99/월~ | 키 | 조건부 | ② https://gnews.io/pricing · https://apiterms.com/api/gnews.io/ |
| NewsData.io | 메타데이터. 전문은 유료 | 206개국 80+ 언어. `category`(lifestyle 등) 필터 | 무료 하루 200크레딧(크레딧당 10건) | 키 | 조건부 | ② https://newsdata.io/blog/pricing-plan-in-newsdata-io/ |
| Event Registry (NewsAPI.ai) | **본문 포함**(`articleBodyLen=-1`), DMOZ 카테고리 | 150,000+ 소스, 50+ 언어 | 무료 2,000토큰(최근 30일 검색 1토큰), 유료 5K 토큰 $90/월 | 키 | 조건부 | ② https://newsapi.ai/plans · https://newsapi.ai/documentation?tab=searchArticles |
| 네이버 검색 API(뉴스) | 제목·링크·요약 ③(블로그 API 와 같은 구조로 추정) | 한국 | 하루 25,000회 | 키 | 조건부 | ② https://choonghyunryu.github.io/posts/2022-03-01-open-api/ |
| (종료) Bing News Search API | 2025-08-11 퇴역, 호출 시 410 | — | — | — | 불가 | ② https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement |

---

## 2. 어댑터 하나로 여러 곳을 먹는 플랫폼 후보

| 유형 | 플랫폼(어댑터 하나) | 먹는 곳 | 근거 |
|---|---|---|---|
| 1 | **Condé Nast `/feed/rss`** | vogue.com, vogue.fr, glamourmagazine.co.uk. vogue.co.uk·vogue.it·vogue.co.jp·gq 계열도 같은 경로일 가능성 ③ | ② 두 곳 확인(Feedspot) |
| 1 | **Hearst US `/rss/{섹션}.xml`** | harpersbazaar.com, elle.com (+ Cosmopolitan·Esquire US ③) | ② Feedspot |
| 1·2·6 | **WordPress `/category/{x}/feed/`** (지금 쓰는 것) | 두산매거진 4곳·marieclaire(기존), WWD(VIP), 일본 MEN'S NON-NO·FUDGE·Oggi·Houyhnhnm ③, Pambianco·华丽志 ③, 유럽 개인 블로그 다수 | ② 피드 URL 꼴 · ③ 플랫폼 판정 |
| 2 | **FashionNetwork 판별 `/rss/`** | 미·영·프·이·일·중·인도 등 15판 — **유형 2에서 국가 커버리지가 가장 넓은 단일 어댑터** | ② https://us.fashionnetwork.com/about/ |
| 2 | Arc XP `arc/outboundfeeds/rss/` | BoF (Arc XP 를 쓰는 다른 매체도 같은 경로 ③) | ② |
| 2 | 국내 인터넷신문 CMS `/rss/allArticle.xml` | 한국섬유신문·국제섬유신문 ③, 그 밖의 국내 업계지 다수 ③ | ② 경로 사례, ③ 적용 |
| 4 | **보도자료 배포사 RSS** — PR Newswire(본판·APAC), Business Wire, GlobeNewswire, PR TIMES, 뉴스와이어 | 수천 개 브랜드의 보도자료. 업종 필터(Fashion)가 배포사 쪽에 이미 있음 | ② #1.4 |
| 5 | Reddit `.rss`(또는 승인 API) | 서브레딧 전부 | ② |
| 5 | XenForo `forums/{x}/index.rss` · Invision 포럼 RSS | Styleforum ③, tFS ③, Superfuture ③ | ② 규칙 · ③ 적용 |
| 6 | **Substack `/feed`** | 발행물 전부(패션·뷰티 랭킹 페이지로 발견) | ② |
| 6 | **Medium `/feed/tag/{태그}`** | 태그 하나로 여러 작가 | ② |
| 6 | Ghost `/rss/`, Blogger `/feeds/posts/default`, Squarespace `?format=rss`, Shopify `/blogs/x.atom` | 개인 블로그·브랜드 블로그 | ② |
| 6 | **note.com `/rss`**, **Ameba `rss20.xml`**, **Hatena `/rss`** | 일본 개인 블로그 | ② |
| 6 | **네이버 블로그 `rss.blog.naver.com/{id}.xml`** + 네이버 검색 API(발견) | 한국 블로그 | ② |
| 6 | 티스토리 `/rss` | 한국 블로그 | ② |
| 7 | YouTube Data API(`videos.list`·`commentThreads.list`) + 채널 RSS | 채널 전부의 제목·설명·댓글 | ② |
| 9 | GDELT DOC API · Google News RSS · CC-NEWS | 매체 목록 자체를 넓힘 | ② |
| 참고 | **RSSHub**(자체 호스팅 변환기) | 웨이보·샤오홍슈·豆瓣·Bilibili 등 중국 플랫폼을 RSS 로. 단 **쿠키 설정이나 Puppeteer(헤드리스 브라우저)** 를 요구하는 경로가 많다 | ② https://docs.rsshub.app/deploy/config · https://github.com/DIYgod/RSSHub/pull/17228/files |

뜻을 풀면 이렇다. 전문 RSS 를 읽는 **범용 RSS/Atom 어댑터 하나**가 유형 1·2·4·6 의 대부분을 덮는다. 플랫폼마다 달라지는 건 "피드 주소를 만드는 규칙"뿐이다. 차이가 크게 나는 건 **피드가 전문을 주는지, 요약만 주는지**다. 요약만 주는 곳은 기사 페이지를 따로 받아야 하므로, 지금의 목록 HTML 어댑터와 같은 부담이 생긴다. — 한 마디로, 어댑터는 RSS 하나로 모이고 갈림길은 전문 여부다. (확신)

---

## 3. 유형 9 상세 — 패션 기사 골라내기, 갱신 주기, 비용

### 3.1 GDELT DOC 2.0

- **골라내는 방법.**
  - 테마: GKG 테마 조회 파일에서 FASHION·CLOTHING·APPAREL·LUXURY·BEAUTY 같은 테마를 **찾지 못했다**(② http://data.gdeltproject.org/api/v2/guides/LOOKUP-GKGTHEMES.TXT). 다만 파일이 커서 요약 도구가 일부만 봤을 수 있다(③). 테마로 거르는 길은 막혀 있다고 보는 게 안전하다.
  - 키워드: 비영어 기사도 **영어 기계번역본에 대해 검색**된다(②). 그래서 `"fashion week" OR runway OR couture` 같은 영어 키워드로 일본어·중국어·한국어 기사도 걸린다. 번역 품질 때문에 재현율은 ③.
  - 도메인: `domainis:vogue.co.jp` 처럼 매체를 지정하면 그 매체의 URL 목록이 나온다. **패션 매체 도메인 목록을 먼저 만들고 → `domainis:` 로 URL 을 뽑는** 방식이 가장 정밀하다(③).
  - 국가·언어: `sourcecountry:`(FIPS 두 글자 — 한국 KS, 일본 JA, 중국 CH, 프랑스 FR, 이탈리아 IT, 영국 UK, 미국 US ③), `sourcelang:`(②).
  - 패션 매체가 GDELT 의 감시 대상에 얼마나 들어 있는지는 **모른다**. GDELT 는 영어권·서구 편향이 지적된다(② https://www.mdpi.com/2306-5729/10/10/158 검색 스니펫).
- **주는 것:** URL·제목·날짜·도메인·언어·국가. **본문은 없다** — 본문은 원 매체를 쳐서 받아야 하므로, 결국 매체별 게이트(#source-discovery 의 두 게이트)로 돌아온다.
- **갱신:** 15분 단위(②). 창은 최근 3개월 롤링(②). 그 이전은 GKG 원시 파일이나 BigQuery.
- **비용·한도:** 무료, 키 없음. 5초당 1요청(②), 한 번 최대 250건(②).

### 3.2 CC-NEWS

- **골라내는 방법.** URL 인덱스가 없으니 WARC 를 받아 **호스트 목록으로 거른다**(news-please 의 `my_filter_valid_hosts` 가 이 방식 ②). URL 경로의 `/fashion/`, `/style/`, `/mode/`, `/moda/`, `/时尚/` 같은 조각으로 한 번 더 거를 수 있다(③).
- **걸리는 것:** 크롤러가 RSS/Atom 피드와 뉴스 사이트맵에서 링크를 찾는다(② https://github.com/commoncrawl/news-crawl). 시드는 사람이 모은 목록과 dmoz 에서 캔 약 6천 피드(②). robots.txt 금지는 이후 수집을 멈춘다(② https://www.digitalapplied.com/blog/publishers-common-crawl-ai-training-data-showdown-2026). 우리 실측(web-collect.md #2)에서 두산매거진 4곳·허스트중앙 2곳이 **CCBot 을 전면 금지**하므로, 한국 패션 매거진은 CC-NEWS 에 거의 없을 것이다(③, 근거는 ① robots 실측).
- **주는 것:** 원문 HTML 전체 — 본문 추출은 우리 몫. 대상 사이트를 치지 않고 본문을 얻는 **유일한 경로**다.
- **갱신:** 매일 WARC 공개(②).
- **비용·한도:** 무료. 부담은 용량이다. 2016년 공개 당시 하루 약 1GB 압축(②). 지금 규모는 확인 못 함(③ — 훨씬 크다).

### 3.3 Google News RSS

- **골라내는 방법.** `q=site:vogue.co.jp when:1d` 처럼 **매체 도메인 + 기간**으로 부르거나, `q=패션위크` 처럼 키워드로 부른다. 국가판은 `hl=ja&gl=JP&ceid=JP:ja` 처럼 셋을 맞춘다(②). 토픽 피드 `rss/topics/{ID}` 도 있지만 ID 가 불투명하고 302 로 바뀐다(②).
- **주는 것:** 제목·출처 이름·날짜. 링크는 인코딩된 리다이렉트라 원 URL 복원에 비공식 호출이 더 필요하다(②). 설명은 자주 비어 있다(②).
- **갱신:** 실시간에 가깝지만, 결과가 오래된 기사 쪽으로 치우친다는 측정이 있다(② cloro, 중간값 6.6일).
- **비용·한도:** 무료. 피드당 약 100건, 페이지 넘김 없음(②). 요청 빈도 한도는 공개된 게 없다(③).

### 3.4 상용 뉴스 API

| API | 패션 거르기 | 본문 | 무료 한도 |
|---|---|---|---|
| NewsAPI.org | `q=` 키워드, `domains=` | 스니펫만 | 하루 100, 24시간 지연, 운영 금지 (②) |
| GNews | `q=`, 국가·언어 | 유료만 | 하루 100, 12시간 지연 (②) |
| NewsData.io | `category=lifestyle`(②) + 키워드 | 유료만 | 하루 200크레딧 (②) |
| Event Registry | DMOZ 카테고리(예: `dmoz/Shopping/Clothing` 같은 계열 ③), 키워드, 소스 URI | **무료에서도 본문 필드 요청 가능**(요금제별 제한 여부 ③) | 2,000토큰 (②) |

---

## 4. 확인 못 한 것

1. **각 피드가 전문인지 요약인지.** Condé Nast·Hearst·FashionNetwork·WWD·Fashionsnap·Highsnobiety·Dazed 모두 모른다. 우리 규칙상 AI 가 대상 사이트를 칠 수 없으니, 팀이 프로필 실측(①)으로 재야 한다.
2. Feedspot 에 올라 있는 피드 URL 이 **지금 살아 있는지**.
3. Vogue UK·Italia·Japan·China 가 Condé Nast 공통 `/feed/rss` 를 쓰는지.
4. 일본 繊研新聞·Fashion Press·WWDJAPAN, 이탈리아 Pambianco, 한국 패션비즈·어패럴뉴스의 RSS 유무와 페이월 비율.
5. SSENSE·MR PORTER·END.·29CM·W컨셉·무신사 콘텐츠의 **JS 렌더링 필수 여부와 봇 차단 서비스 종류**. 대형 리테일러라 걸려 있을 거라는 건 추정일 뿐이다.
6. 프랑스·이탈리아의 패션 전용 커뮤니티. 찾지 못했다.
7. Styleforum 의 포럼 소프트웨어(XenForo 인지), Superfuture 구독제가 비회원 열람을 막는지.
8. 5ch·에펨코리아의 Cloudflare 챌린지 여부. 디시인사이드 공식 RSS 유무.
9. 네이버 블로그 RSS 의 `description` 이 전문인지 요약인지. 네이버 뉴스 검색 API 의 응답 필드(블로그 API 와 같다고 추정만 했다). 네이버 개발자 문서는 WebFetch 가 막혀 직접 못 읽었다.
10. GDELT 가 패션 매체(특히 한·일·중)를 얼마나 감시하는지, 그리고 GKG 테마 전체 목록에 패션 테마가 정말 없는지(조회 도구가 파일 일부만 봤을 수 있다).
11. CC-NEWS 의 현재 일일 규모와 패션 도메인 포함 여부.
12. Google News RSS 의 요청 빈도 한도, 차단 조건.
13. Event Registry 무료 요금제에서 본문을 실제로 주는지, DMOZ 패션 카테고리의 정확한 URI.
14. 美通社(PR Newswire Asia)·PR TIMES 카테고리 RSS 의 정확한 주소.
15. niconico·네이버TV·抖音의 자막·설명 접근 경로.
16. Instagram `recent_media` 가 돌려주는 기간(24시간인지)과 건수.
17. Medium·Substack 이 Cloudflare 등으로 피드 요청을 막는지(Cloudflare 봇 차단이 RSS 리더를 막는 일반 사례는 있다 ② https://openrss.org/blog/using-cloudflare-on-your-website-could-be-blocking-rss-users).
