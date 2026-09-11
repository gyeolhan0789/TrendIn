package com.forever102.test;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberDomain;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.member.domain.SavedTrend;
import com.forever102.member.repository.MemberDomainRepository;
import com.forever102.member.repository.MemberInterestKeywordRepository;
import com.forever102.member.repository.MemberRepository;
import com.forever102.member.repository.SavedTrendRepository;
import com.forever102.notification.domain.Notification;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.Content;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.KeywordMetricHistory;
import com.forever102.trend.domain.KeywordRelation;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.repository.ContentRepository;
import com.forever102.trend.repository.KeywordMetricHistoryRepository;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.KeywordRelationRepository;
import com.forever102.trend.repository.KeywordRepository;
import com.forever102.trend.repository.TrendRepository;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * local 프로필에서 서버가 뜰 때 통합 테스트용 더미 데이터를 넣는다.
 *
 * <p>키워드는 두 층으로 나눈다. 화면에 실제로 보여줄 핵심 키워드에는 트렌드·시계열·콘텐츠·연관 관계를
 * 모두 붙이고, 검색과 페이지네이션을 확인할 대량 키워드에는 지표만 붙인다.
 * 모든 키워드에 시계열과 콘텐츠를 붙이면 기동이 크게 느려지기 때문이다.
 *
 * <p>지표의 기간 경계는 {@link AnalysisWindow#completed}가 계산하는 값과 정확히 같아야 조회에 잡히므로,
 * 고정 날짜가 아니라 실행 시각 기준으로 만든다. 언제 띄워도 트렌드 목록과 상세가 비어 보이지 않는다.
 *
 * <p>모든 계정의 비밀번호는 {@code password123!}이다.
 */
@Component
@Profile("local")
@RequiredArgsConstructor
@Slf4j
public class TestInitialize implements ApplicationRunner {

    private static final String RAW_PASSWORD = "password123!";
    /** 데이터가 매번 같아야 재현 가능한 테스트가 되므로 시드를 고정한다. */
    private static final Random RANDOM = new Random(20260911L);
    /** 대량 키워드 중 트렌드를 붙일 비율. 트렌드 목록 페이지네이션을 확인할 만큼만 만든다. */
    private static final int BULK_TREND_EVERY = 3;
    /** 언급 순위를 매길 상위 개수. 나머지는 rank가 null이다. */
    private static final int RANKED_LIMIT = 50;

    private final MemberRepository memberRepository;
    private final MemberDomainRepository memberDomainRepository;
    private final MemberInterestKeywordRepository interestKeywordRepository;
    private final SavedTrendRepository savedTrendRepository;
    private final NotificationRepository notificationRepository;
    private final KeywordRepository keywordRepository;
    private final TrendRepository trendRepository;
    private final KeywordMetricRepository metricRepository;
    private final KeywordMetricHistoryRepository historyRepository;
    private final KeywordRelationRepository relationRepository;
    private final ContentRepository contentRepository;
    private final PasswordEncoder passwordEncoder;
    private final Clock trendClock;

    /** 핵심 키워드는 이름으로 찾아 쓰고, 대량 키워드는 순서대로 훑는다. */
    private record Keywords(Map<String, Keyword> curated, List<Keyword> all) {
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (memberRepository.count() > 0) {
            log.info("[TestInitialize] 이미 데이터가 있어 더미 생성을 건너뛴다.");
            return;
        }

        long startedAt = System.currentTimeMillis();

        Keywords keywords = createKeywords();
        Map<String, Trend> trends = createCuratedTrends(keywords.curated());
        int bulkTrends = createBulkTrends(keywords);
        createMetrics(keywords.all());
        createHistories(keywords.curated());
        createRelations(keywords);
        createContents(keywords.curated());
        createMembers(keywords.curated(), trends);

        log.info("[TestInitialize] 더미 데이터 생성 완료 ({}ms). "
                        + "키워드 {}건(핵심 {}건), 트렌드 {}건, 회원 {}건. 공통 비밀번호: {}",
                System.currentTimeMillis() - startedAt,
                keywords.all().size(), keywords.curated().size(),
                trends.size() + bulkTrends, memberRepository.count(), RAW_PASSWORD);
    }

    // ---------------------------------------------------------------- 키워드

    private Keywords createKeywords() {
        Map<String, Keyword> curated = new LinkedHashMap<>();
        List<Keyword> all = new ArrayList<>();

        curatedNames().forEach((name, domain) -> {
            Keyword keyword = keywordRepository.save(new Keyword(name, domain));
            curated.put(name, keyword);
            all.add(keyword);
        });

        bulkNames(curated.keySet()).forEach((name, domain) ->
                all.add(keywordRepository.save(new Keyword(name, domain))));

        return new Keywords(curated, all);
    }

    /**
     * 화면에 실제로 보여줄 키워드. 한글과 영문을 섞고,
     * 검색 테스트를 위해 접두어를 공유하는 묶음(Spring·스프링)과 트렌드가 없는 키워드를 함께 둔다.
     */
    private Map<String, Domain> curatedNames() {
        Map<String, Domain> names = new LinkedHashMap<>();
        List<String> develop = List.of(
                // 영문
                "Spring Boot", "Spring Security", "Spring AI", "Spring Batch",
                "Kotlin", "Rust", "WebAssembly", "Kubernetes",
                "GraphQL", "gRPC", "Vector Database", "LLM Agent",
                "Observability", "Edge Runtime", "Server Component", "Data Mesh",
                // 한글
                "스프링 부트", "스프링 시큐리티", "코틀린", "러스트",
                "쿠버네티스", "벡터 검색", "대규모 언어 모델", "관측 가능성",
                "분산 추적", "동시성 제어", "서버리스 런타임", "타입 안정성",
                "슬로우 쿼리", "커넥션 풀", "무중단 배포", "장애 대응");
        List<String> fashion = List.of(
                // 영문
                "Ballet Sneakers", "Quiet Luxury", "Gorpcore", "Denim Maxi Skirt",
                "Sheer Layering", "Chrome Accessory", "Varsity Jacket", "Balaclava",
                "Suede Loafer", "Cargo Skirt", "Data Knit", "Bold Shoulder",
                // 한글
                "발레코어", "조용한 럭셔리", "고프코어", "시스루 레이어드",
                "메탈릭 액세서리", "바시티 재킷", "발라클라바", "스웨이드 로퍼",
                "카고 스커트", "오버핏 블레이저", "빈티지 데님", "니트 베스트");

        develop.forEach(name -> names.put(name, Domain.DEVELOP));
        fashion.forEach(name -> names.put(name, Domain.FASHION));
        return names;
    }

    /**
     * 검색·페이지네이션 확인용 대량 키워드를 조합으로 만든다.
     * 한글과 영문을 모두 만들어 어느 쪽으로 검색해도 결과가 충분히 나온다.
     */
    private Map<String, Domain> bulkNames(Set<String> reserved) {
        Map<String, Domain> names = new LinkedHashMap<>();

        combine(names, Domain.DEVELOP, reserved,
                List.of("실시간", "분산", "경량", "고성능", "자동화", "안전한", "확장형", "비동기",
                        "무중단", "지능형", "클라우드", "컨테이너", "엣지", "온프레미스",
                        "멀티테넌트", "이벤트 기반", "선언형"),
                List.of("캐시", "트랜잭션", "인덱싱", "배포", "모니터링", "로깅", "추적", "메시지 큐",
                        "스트리밍", "인증", "권한 관리", "암호화", "백업", "복제", "샤딩",
                        "검색 엔진", "추천 엔진", "스케줄러", "워크플로", "파이프라인"));

        combine(names, Domain.DEVELOP, reserved,
                List.of("Distributed", "Serverless", "Reactive", "Streaming", "Realtime",
                        "Edge", "Zero Trust", "Adaptive", "Federated", "Incremental"),
                List.of("Cache", "Tracing", "Indexing", "Pipeline", "Runtime", "Scheduler",
                        "Registry", "Gateway", "Mesh", "Profiler", "Compiler", "Router",
                        "Store", "Loader", "Planner"));

        combine(names, Domain.FASHION, reserved,
                List.of("오버핏", "크롭", "와이드", "슬림", "빈티지", "미니멀", "레이어드", "메탈릭",
                        "파스텔", "모노톤", "워시드", "플리츠", "셔링", "패치워크", "리버시블",
                        "하이웨이스트", "루즈핏"),
                List.of("니트", "블레이저", "카디건", "셔츠", "데님 팬츠", "스커트", "원피스", "코트",
                        "재킷", "베스트", "슬랙스", "점퍼", "후디", "머플러", "로퍼",
                        "부츠", "스니커즈", "가방", "벨트", "주얼리"));

        combine(names, Domain.FASHION, reserved,
                List.of("Sheer", "Chrome", "Oversized", "Cropped", "Quilted",
                        "Pleated", "Washed", "Muted", "Structured", "Utility"),
                List.of("Blazer", "Cardigan", "Trousers", "Loafer", "Tote", "Scarf", "Knit",
                        "Parka", "Skirt", "Boots", "Belt", "Vest", "Hoodie", "Jacket",
                        "Sneakers"));

        return names;
    }

    private void combine(Map<String, Domain> names, Domain domain, Set<String> reserved,
            List<String> modifiers, List<String> bases) {
        Set<String> seen = new LinkedHashSet<>(reserved);
        seen.addAll(names.keySet());
        for (String modifier : modifiers) {
            for (String base : bases) {
                String name = modifier + " " + base;
                if (seen.add(name)) {
                    names.put(name, domain);
                }
            }
        }
    }

    // ---------------------------------------------------------------- 트렌드

    /**
     * 유형 조합과 AI 분석 유무를 섞는다.
     * 트렌드가 없는 키워드도 남겨 키워드 검색에서 trend가 null인 경우를 볼 수 있게 한다.
     */
    private Map<String, Trend> createCuratedTrends(Map<String, Keyword> keywords) {
        OffsetDateTime now = OffsetDateTime.now(trendClock);
        Map<String, Trend> created = new LinkedHashMap<>();

        record Spec(String keyword, List<TrendType> types, String description,
                    String summary, String reason) {
        }

        List<Spec> specs = List.of(
                new Spec("Spring Boot", List.of(TrendType.CURRENT),
                        "자바 백엔드 표준 프레임워크",
                        "4.x 릴리스 이후 마이그레이션 논의가 이어지고 있다.",
                        "릴리스 직후 마이그레이션 가이드 게시물이 급증했다."),
                new Spec("Spring AI", List.of(TrendType.CURRENT, TrendType.RISING),
                        "자바 진영의 LLM 연동 추상화",
                        "LLM 연동을 표준화하려는 시도로 주목받고 있다.",
                        "예제 저장소 스타 수가 2주 사이 크게 늘었다."),
                new Spec("Spring Security", List.of(TrendType.CURRENT),
                        "스프링 인증·인가 모듈", null, null),
                new Spec("Kotlin", List.of(TrendType.CURRENT),
                        "JVM 계열 멀티플랫폼 언어",
                        "서버 사이드 채택 사례가 꾸준히 보고된다.", null),
                new Spec("Rust", List.of(TrendType.CURRENT, TrendType.RISING),
                        "메모리 안전성을 보장하는 시스템 언어",
                        "인프라 도구를 다시 쓰는 사례가 늘고 있다.",
                        "주요 CLI 도구의 재작성 발표가 이어졌다."),
                new Spec("WebAssembly", List.of(TrendType.NEW),
                        "브라우저 밖으로 확장되는 실행 환경", null, null),
                new Spec("Vector Database", List.of(TrendType.RISING, TrendType.NEW),
                        "임베딩 검색에 특화된 저장소",
                        "RAG 구성의 기본 요소로 자리잡는 중이다.",
                        "신규 제품 출시와 벤치마크 글이 동시에 늘었다."),
                new Spec("LLM Agent", List.of(TrendType.CURRENT, TrendType.RISING, TrendType.NEW),
                        "도구를 호출하며 작업을 수행하는 에이전트",
                        "실제 업무 자동화 사례가 공유되기 시작했다.",
                        "프레임워크 비교 글이 전 주 대비 세 배 늘었다."),
                new Spec("Kubernetes", List.of(TrendType.CURRENT),
                        "컨테이너 오케스트레이션 표준", null, null),
                new Spec("Observability", List.of(TrendType.RISING),
                        "분산 시스템 관측 체계",
                        "OpenTelemetry 도입기가 많이 보인다.", null),
                // 한글 키워드 트렌드
                new Spec("스프링 부트", List.of(TrendType.CURRENT),
                        "국내 백엔드에서 가장 널리 쓰이는 프레임워크",
                        "버전 업그레이드 경험 공유가 활발하다.",
                        "기술 블로그 연재가 이어지고 있다."),
                new Spec("대규모 언어 모델", List.of(TrendType.CURRENT, TrendType.RISING),
                        "서비스에 붙이는 LLM 활용",
                        "사내 도구에 적용한 사례가 늘고 있다.",
                        "도입 후기 글이 꾸준히 올라온다."),
                new Spec("벡터 검색", List.of(TrendType.RISING, TrendType.NEW),
                        "임베딩 기반 유사도 검색",
                        "검색 품질 개선 목적의 도입이 많다.", null),
                new Spec("무중단 배포", List.of(TrendType.CURRENT),
                        "서비스 중단 없이 새 버전을 올리는 방식", null, null),
                new Spec("분산 추적", List.of(TrendType.RISING),
                        "요청 흐름을 서비스 간에 추적하는 기법",
                        "장애 분석 시간을 줄였다는 후기가 많다.", null),
                new Spec("Ballet Sneakers", List.of(TrendType.CURRENT, TrendType.RISING),
                        "발레 슈즈를 닮은 납작한 스니커즈",
                        "봄 시즌 착장 사진이 빠르게 늘고 있다.",
                        "스트리트 스냅 태그 수가 2주 연속 증가했다."),
                new Spec("Quiet Luxury", List.of(TrendType.CURRENT),
                        "로고를 드러내지 않는 고급스러움",
                        "소재 중심 소비로 흐름이 옮겨가는 중이다.", null),
                new Spec("Gorpcore", List.of(TrendType.CURRENT, TrendType.NEW),
                        "아웃도어 기능성을 일상복으로",
                        "등산복 브랜드의 도심 착장이 확산되고 있다.",
                        "아웃도어 브랜드 협업 발표가 몰렸다."),
                new Spec("Sheer Layering", List.of(TrendType.NEW),
                        "비치는 소재를 겹쳐 입는 방식", null, null),
                new Spec("Chrome Accessory", List.of(TrendType.RISING),
                        "금속 광택을 살린 액세서리",
                        "실버 계열 주얼리 언급이 늘었다.", null),
                new Spec("Balaclava", List.of(TrendType.CURRENT),
                        "얼굴까지 감싸는 니트 모자", null, null),
                // 한글 키워드 트렌드
                new Spec("발레코어", List.of(TrendType.CURRENT, TrendType.RISING),
                        "발레복에서 출발한 여성복 흐름",
                        "리본과 메리제인 조합이 자주 보인다.",
                        "봄 시즌 검색량이 두 배로 늘었다."),
                new Spec("조용한 럭셔리", List.of(TrendType.CURRENT),
                        "로고 없이 소재로 보여주는 고급스러움",
                        "캐시미어와 울 언급이 함께 늘었다.", null),
                new Spec("고프코어", List.of(TrendType.CURRENT, TrendType.NEW),
                        "등산복을 일상복으로 입는 방식", null, null),
                new Spec("빈티지 데님", List.of(TrendType.RISING),
                        "오래된 느낌을 살린 데님",
                        "워시드 가공 제품 문의가 늘었다.", null),
                new Spec("메탈릭 액세서리", List.of(TrendType.NEW),
                        "광택 있는 금속 소재 소품", null, null));

        for (Spec spec : specs) {
            Trend trend = new Trend(keywords.get(spec.keyword()), spec.types(),
                    spec.description(), spec.summary(), spec.reason(),
                    now.minusHours(RANDOM.nextInt(48)));
            created.put(spec.keyword(), trendRepository.save(trend));
        }
        return created;
    }

    /**
     * 대량 키워드 일부에 트렌드를 붙여 트렌드 목록 페이지네이션을 확인할 수 있게 한다.
     * 유형은 세 가지를 돌아가며 배정해 필터마다 결과가 나오도록 한다.
     */
    private int createBulkTrends(Keywords keywords) {
        OffsetDateTime now = OffsetDateTime.now(trendClock);
        List<List<TrendType>> typeCycle = List.of(
                List.of(TrendType.CURRENT),
                List.of(TrendType.RISING),
                List.of(TrendType.NEW),
                List.of(TrendType.CURRENT, TrendType.RISING),
                List.of(TrendType.CURRENT, TrendType.NEW));

        int created = 0;
        int index = 0;
        for (Keyword keyword : keywords.all()) {
            if (keywords.curated().containsKey(keyword.getName())) {
                continue;
            }
            index++;
            if (index % BULK_TREND_EVERY != 0) {
                continue;
            }
            trendRepository.save(new Trend(
                    keyword,
                    typeCycle.get(created % typeCycle.size()),
                    "%s 관련 흐름".formatted(keyword.getName()),
                    // 대량 데이터에는 AI 분석을 넣지 않아 null 표기를 함께 확인할 수 있다.
                    null, null,
                    now.minusHours(RANDOM.nextInt(72))));
            created++;
        }
        return created;
    }

    // ---------------------------------------------------------------- 지표

    /**
     * 모든 키워드에 대해 세 기간의 완료 구간 지표를 만든다.
     * 키워드 검색 응답도 지표를 함께 보여주므로 대량 키워드까지 채운다.
     * 급증·급감·직전 언급량 0(증가율 null)·순위 없음을 섞는다.
     */
    private void createMetrics(List<Keyword> keywords) {
        for (AnalysisPeriod period : AnalysisPeriod.values()) {
            AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
            createDomainMetrics(keywords, period, window, Domain.DEVELOP);
            createDomainMetrics(keywords, period, window, Domain.FASHION);
        }
    }

    private void createDomainMetrics(List<Keyword> keywords, AnalysisPeriod period,
            AnalysisWindow window, Domain domain) {
        int rank = 1;
        for (Keyword keyword : keywords) {
            if (keyword.getDomain() != domain || isMetricExcluded(keyword, period)) {
                continue;
            }
            long previous = previousMentionCount(keyword, period);
            long mention = mentionCount(keyword, period, previous);
            long growthAmount = mention - previous;
            BigDecimal growthRate = previous == 0 ? null
                    : BigDecimal.valueOf(growthAmount * 100.0 / previous)
                            .setScale(1, RoundingMode.HALF_UP);

            metricRepository.save(KeywordMetric.builder()
                    .keyword(keyword)
                    .period(period)
                    .periodStart(window.getRecentStart())
                    .periodEnd(window.getRecentEnd())
                    .mentionCount(mention)
                    .previousMentionCount(previous)
                    .growthAmount(growthAmount)
                    .growthRate(growthRate)
                    // 순위를 매기지 않은 키워드도 섞어 mentionRank가 null인 경우를 만든다.
                    .mentionRank(rank > RANKED_LIMIT ? null : rank)
                    .build());
            rank++;
        }
    }

    /** 24H 지표가 없는 트렌드를 만들어 "분석 결과 없음" 화면을 재현한다. */
    private boolean isMetricExcluded(Keyword keyword, AnalysisPeriod period) {
        return period == AnalysisPeriod.HOURS_24
                && ("Sheer Layering".equals(keyword.getName())
                || "메탈릭 액세서리".equals(keyword.getName()));
    }

    /** 직전 언급량 0을 만들어 증가율이 null인 경우를 재현한다. */
    private long previousMentionCount(Keyword keyword, AnalysisPeriod period) {
        if ("Vector Database".equals(keyword.getName()) || "벡터 검색".equals(keyword.getName())) {
            return 0L;
        }
        long base = 40 + RANDOM.nextInt(400);
        return base * periodWeight(period);
    }

    /** 급감 사례를 넣어 증가율이 음수인 경우를 재현한다. */
    private long mentionCount(Keyword keyword, AnalysisPeriod period, long previous) {
        if ("Balaclava".equals(keyword.getName()) || "발라클라바".equals(keyword.getName())) {
            return Math.max(0, previous / 3);
        }
        if (previous == 0) {
            return (12 + RANDOM.nextInt(80)) * periodWeight(period);
        }
        return previous + RANDOM.nextInt((int) Math.max(2, previous));
    }

    private long periodWeight(AnalysisPeriod period) {
        return switch (period) {
            case HOURS_24 -> 1L;
            case DAYS_7 -> 6L;
            case DAYS_30 -> 24L;
        };
    }

    // ---------------------------------------------------------------- 시계열

    /**
     * 기간별 버킷 크기에 맞춰 시계열을 채운다. 핵심 키워드에만 붙인다.
     * 일부 버킷을 비워 두어 서비스가 0으로 메우는 동작을 확인할 수 있게 한다.
     */
    private void createHistories(Map<String, Keyword> keywords) {
        List<String> targets = List.of(
                "Spring Boot", "Spring AI", "LLM Agent", "Rust",
                "스프링 부트", "대규모 언어 모델", "분산 추적",
                "Ballet Sneakers", "Quiet Luxury", "Gorpcore",
                "발레코어", "조용한 럭셔리", "빈티지 데님");

        for (AnalysisPeriod period : AnalysisPeriod.values()) {
            AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
            Duration bucket = period.getHistoryBucketDuration();

            for (String name : targets) {
                Keyword keyword = keywords.get(name);
                int index = 0;
                for (OffsetDateTime start = window.getRecentStart();
                        start.isBefore(window.getRecentEnd());
                        start = start.plus(bucket)) {
                    index++;
                    // Gorpcore와 빈티지 데님은 중간 버킷을 비워 데이터 구멍이 있는 경우를 만든다.
                    if (("Gorpcore".equals(name) || "빈티지 데님".equals(name)) && index % 4 == 0) {
                        continue;
                    }
                    historyRepository.save(new KeywordMetricHistory(
                            keyword, start, start.plus(bucket), 5 + RANDOM.nextInt(120)));
                }
            }
        }
    }

    // ---------------------------------------------------------------- 연관 키워드

    /**
     * 연관 키워드 조회는 source 기준 단방향이라, 양쪽에서 모두 보이도록 두 방향을 함께 넣는다.
     * 핵심 키워드는 의미가 맞는 쌍으로, 대량 키워드는 같은 분야 안에서 이웃끼리 엮는다.
     */
    private void createRelations(Keywords keywords) {
        record Pair(String source, String target, double score, long coOccurrence) {
        }

        List<Pair> pairs = List.of(
                new Pair("Spring Boot", "Spring Security", 92.5, 480),
                new Pair("Spring Boot", "Spring AI", 78.0, 310),
                new Pair("Spring Boot", "Kotlin", 65.5, 240),
                new Pair("Spring Boot", "Kubernetes", 54.0, 180),
                new Pair("Spring Boot", "스프링 부트", 96.0, 520),
                new Pair("Spring AI", "LLM Agent", 88.0, 420),
                new Pair("Spring AI", "Vector Database", 81.5, 360),
                new Pair("LLM Agent", "Vector Database", 76.0, 290),
                new Pair("LLM Agent", "대규모 언어 모델", 91.0, 450),
                new Pair("대규모 언어 모델", "벡터 검색", 84.5, 380),
                new Pair("벡터 검색", "Vector Database", 89.0, 400),
                new Pair("Rust", "WebAssembly", 84.0, 350),
                new Pair("Rust", "러스트", 95.0, 500),
                new Pair("Kubernetes", "Observability", 71.0, 260),
                new Pair("Kubernetes", "쿠버네티스", 94.5, 490),
                new Pair("Observability", "분산 추적", 86.0, 340),
                new Pair("분산 추적", "관측 가능성", 82.0, 300),
                new Pair("무중단 배포", "장애 대응", 68.0, 210),
                new Pair("동시성 제어", "타입 안정성", 49.5, 130),
                new Pair("슬로우 쿼리", "커넥션 풀", 73.5, 250),
                new Pair("GraphQL", "gRPC", 63.0, 150),
                new Pair("Server Component", "Edge Runtime", 58.5, 130),
                new Pair("Ballet Sneakers", "발레코어", 93.0, 470),
                new Pair("Ballet Sneakers", "Quiet Luxury", 74.0, 300),
                new Pair("Ballet Sneakers", "Suede Loafer", 69.5, 210),
                new Pair("Quiet Luxury", "조용한 럭셔리", 95.5, 510),
                new Pair("Quiet Luxury", "Chrome Accessory", 61.0, 175),
                new Pair("Gorpcore", "고프코어", 94.0, 480),
                new Pair("Gorpcore", "Cargo Skirt", 66.5, 190),
                new Pair("Gorpcore", "Balaclava", 55.0, 140),
                new Pair("발레코어", "니트 베스트", 57.5, 160),
                new Pair("조용한 럭셔리", "오버핏 블레이저", 72.0, 240),
                new Pair("빈티지 데님", "카고 스커트", 64.0, 185),
                new Pair("메탈릭 액세서리", "Chrome Accessory", 90.0, 410),
                new Pair("Varsity Jacket", "Denim Maxi Skirt", 47.5, 110),
                new Pair("Sheer Layering", "시스루 레이어드", 92.0, 440),
                new Pair("Sheer Layering", "Bold Shoulder", 52.0, 125));

        OffsetDateTime updatedAt = OffsetDateTime.now(trendClock).minusHours(6);
        for (Pair pair : pairs) {
            saveRelationBothWays(keywords.curated().get(pair.source()),
                    keywords.curated().get(pair.target()),
                    BigDecimal.valueOf(pair.score()), pair.coOccurrence(), updatedAt);
        }

        // 대량 키워드는 같은 분야 안에서 인접한 것끼리 엮어 연관 키워드가 비지 않게 한다.
        for (Domain domain : Domain.values()) {
            List<Keyword> bulk = keywords.all().stream()
                    .filter(keyword -> keyword.getDomain() == domain)
                    .filter(keyword -> !keywords.curated().containsKey(keyword.getName()))
                    .toList();
            for (int i = 0; i + 1 < bulk.size(); i += 4) {
                BigDecimal score = BigDecimal.valueOf(30 + RANDOM.nextInt(60))
                        .setScale(2, RoundingMode.UNNECESSARY);
                saveRelationBothWays(bulk.get(i), bulk.get(i + 1), score,
                        20 + RANDOM.nextInt(300), updatedAt);
            }
        }
    }

    private void saveRelationBothWays(Keyword source, Keyword target, BigDecimal score,
            long coOccurrence, OffsetDateTime updatedAt) {
        relationRepository.save(new KeywordRelation(source, target, score, coOccurrence, updatedAt));
        relationRepository.save(new KeywordRelation(target, source, score, coOccurrence, updatedAt));
    }

    // ---------------------------------------------------------------- 콘텐츠

    /**
     * 한 콘텐츠가 여러 키워드에 걸리는 경우와 본문 키가 없는 경우를 함께 만든다.
     * 페이지네이션을 확인할 수 있도록 인기 키워드에는 콘텐츠를 넉넉히 붙인다.
     */
    private void createContents(Map<String, Keyword> keywords) {
        record Source(String name, String host) {
        }
        record Volume(String keyword, int count) {
        }

        List<Source> sources = List.of(
                new Source("Tech Blog Weekly", "techblogweekly.example.com"),
                new Source("데브 트렌드", "devtrends.example.com"),
                new Source("Style Journal", "stylejournal.example.com"),
                new Source("패션 리포트", "fashionreport.example.com"));

        // Map.of는 순회 순서가 실행마다 달라져 URL·발행 시각이 흔들리므로 순서가 있는 목록으로 둔다.
        List<Volume> volumes = List.of(
                new Volume("Spring Boot", 12), new Volume("Spring AI", 9),
                new Volume("LLM Agent", 8), new Volume("Rust", 6),
                new Volume("Kubernetes", 4), new Volume("스프링 부트", 10),
                new Volume("대규모 언어 모델", 8), new Volume("분산 추적", 5),
                new Volume("Ballet Sneakers", 11), new Volume("Quiet Luxury", 7),
                new Volume("Gorpcore", 5), new Volume("발레코어", 9),
                new Volume("조용한 럭셔리", 6), new Volume("빈티지 데님", 5));

        OffsetDateTime now = OffsetDateTime.now(trendClock);
        int serial = 0;
        for (Volume volume : volumes) {
            Keyword keyword = keywords.get(volume.keyword());
            for (int i = 0; i < volume.count(); i++) {
                serial++;
                Source source = sources.get(
                        keyword.getDomain() == Domain.DEVELOP ? i % 2 : 2 + i % 2);
                OffsetDateTime publishedAt = now.minusHours(3L * serial);

                // 일부 콘텐츠는 키워드 두 개에 함께 걸어 다대다 관계를 확인할 수 있게 한다.
                Keyword companion = i % 4 == 0 ? findCompanion(keywords, keyword) : null;
                String title = companion == null
                        ? "%s 관련 리포트 #%d".formatted(keyword.getName(), i + 1)
                        // 두 트렌드 어디에서 보든 제목이 말이 되도록 키워드를 모두 적는다.
                        : "%s와 %s를 함께 다룬 리포트 #%d"
                                .formatted(keyword.getName(), companion.getName(), i + 1);

                Content content = new Content(
                        title,
                        source.name(),
                        "https://%s/articles/%d".formatted(source.host(), serial),
                        // 본문을 아직 수집하지 않은 콘텐츠를 섞는다.
                        i % 3 == 0 ? null : "contents/%d/body.txt".formatted(serial),
                        publishedAt,
                        publishedAt.plusMinutes(30));
                content.addKeyword(keyword);
                if (companion != null) {
                    content.addKeyword(companion);
                }
                contentRepository.save(content);
            }
        }
    }

    /** 같은 분야의 다른 키워드를 하나 골라 콘텐츠를 두 키워드에 걸친다. */
    private Keyword findCompanion(Map<String, Keyword> keywords, Keyword keyword) {
        return keywords.values().stream()
                .filter(other -> other.getDomain() == keyword.getDomain())
                .filter(other -> !other.getName().equals(keyword.getName()))
                .findFirst()
                .orElse(null);
    }

    // ---------------------------------------------------------------- 회원

    /**
     * 온보딩 전후, 분야 한 개·두 개, 관심 키워드 없음·많음, 저장 트렌드와 알림 유무를 모두 만든다.
     */
    private void createMembers(Map<String, Keyword> keywords, Map<String, Trend> trends) {
        String encoded = passwordEncoder.encode(RAW_PASSWORD);

        // 1) 개발 분야만 고른 헤비 유저. 관심 키워드와 저장 트렌드, 알림이 모두 많다.
        Member developer = saveMember("dev@example.com", encoded, "백엔드개발자", true);
        addDomains(developer, Domain.DEVELOP);
        addInterestKeywords(developer, keywords,
                "Spring Boot", "Spring AI", "Kotlin", "Kubernetes", "LLM Agent", "Rust",
                "스프링 부트", "대규모 언어 모델");
        addSavedTrends(developer, trends, "Spring Boot", "Spring AI", "LLM Agent", "Rust",
                "스프링 부트", "대규모 언어 모델");
        addNotifications(developer, trends, 12, 5);

        // 2) 패션 분야만 고른 사용자.
        Member stylist = saveMember("fashion@example.com", encoded, "스타일리스트", true);
        addDomains(stylist, Domain.FASHION);
        addInterestKeywords(stylist, keywords,
                "Ballet Sneakers", "Quiet Luxury", "Gorpcore", "발레코어", "조용한 럭셔리");
        addSavedTrends(stylist, trends, "Ballet Sneakers", "Quiet Luxury", "발레코어");
        addNotifications(stylist, trends, 6, 6);

        // 3) 두 분야를 모두 고른 사용자. 분야 교체 시 키워드가 함께 정리되는지 확인하기 좋다.
        Member both = saveMember("both@example.com", encoded, "두분야모두", true);
        addDomains(both, Domain.DEVELOP, Domain.FASHION);
        addInterestKeywords(both, keywords,
                "Spring Boot", "Vector Database", "Ballet Sneakers", "Chrome Accessory",
                "벡터 검색", "메탈릭 액세서리");
        addSavedTrends(both, trends, "Spring Boot", "Ballet Sneakers", "Gorpcore", "벡터 검색");
        addNotifications(both, trends, 4, 0);

        // 4) 온보딩을 마치지 않은 신규 가입자. 분야도 키워드도 없다.
        saveMember("newbie@example.com", encoded, "신규가입자", false);

        // 5) 분야는 골랐지만 관심 키워드가 없는 사용자. 추천 키워드가 비는 경우를 만든다.
        Member emptyKeyword = saveMember("nokeyword@example.com", encoded, "키워드없음", true);
        addDomains(emptyKeyword, Domain.DEVELOP);

        // 6) 관심 키워드가 많아 페이지네이션을 확인할 수 있는 사용자.
        Member heavy = saveMember("heavy@example.com", encoded, "관심많은사람", true);
        addDomains(heavy, Domain.DEVELOP, Domain.FASHION);
        addInterestKeywords(heavy, keywords,
                "Spring Boot", "Spring Security", "Spring AI", "Spring Batch", "Kotlin",
                "Rust", "WebAssembly", "Kubernetes", "GraphQL", "gRPC",
                "스프링 부트", "스프링 시큐리티", "코틀린", "러스트", "쿠버네티스",
                "벡터 검색", "대규모 언어 모델", "관측 가능성", "분산 추적", "무중단 배포",
                "Ballet Sneakers", "Quiet Luxury", "Gorpcore", "Varsity Jacket",
                "발레코어", "조용한 럭셔리", "고프코어", "빈티지 데님");
        addSavedTrends(heavy, trends,
                "Spring Boot", "Spring AI", "Spring Security", "Kotlin", "Rust",
                "Kubernetes", "Observability", "스프링 부트", "대규모 언어 모델", "분산 추적",
                "무중단 배포", "Ballet Sneakers", "Quiet Luxury", "Gorpcore",
                "Chrome Accessory", "Balaclava", "발레코어", "조용한 럭셔리", "빈티지 데님");
        addNotifications(heavy, trends, 25, 9);

        // 7) 알림과 저장 트렌드가 하나도 없는 사용자. 빈 목록 응답을 확인한다.
        Member quiet = saveMember("quiet@example.com", encoded, "조용한사용자", true);
        addDomains(quiet, Domain.FASHION);
        addInterestKeywords(quiet, keywords, "Balaclava", "발라클라바");
    }

    private Member saveMember(String email, String encodedPassword, String nickname,
            boolean onboardingCompleted) {
        Member member = Member.create(email, encodedPassword, nickname);
        if (onboardingCompleted) {
            member.completeOnboarding();
        }
        return memberRepository.save(member);
    }

    private void addDomains(Member member, Domain... domains) {
        for (Domain domain : domains) {
            memberDomainRepository.save(MemberDomain.register(member, domain));
        }
    }

    private void addInterestKeywords(Member member, Map<String, Keyword> keywords, String... names) {
        for (String name : names) {
            interestKeywordRepository.save(
                    MemberInterestKeyword.register(member, keywords.get(name)));
        }
    }

    private void addSavedTrends(Member member, Map<String, Trend> trends, String... names) {
        for (String name : names) {
            savedTrendRepository.save(SavedTrend.save(member, trends.get(name)));
        }
    }

    /**
     * 읽음·안읽음을 섞어 안읽은 개수 조회와 일괄 읽음 처리를 확인할 수 있게 한다.
     */
    private void addNotifications(Member member, Map<String, Trend> trends, int total, int unread) {
        List<Trend> pool = new ArrayList<>(trends.values());
        for (int i = 0; i < total; i++) {
            Trend trend = pool.get(i % pool.size());
            Notification notification = Notification.trendChange(
                    member, trend,
                    "관심 키워드 '%s'의 트렌드가 변했습니다.".formatted(trend.getKeyword().getName()),
                    "seed:%s:%d".formatted(member.getEmail(), i));
            Notification saved = notificationRepository.save(notification);
            if (i >= unread) {
                saved.markAsRead();
            }
        }
    }
}
