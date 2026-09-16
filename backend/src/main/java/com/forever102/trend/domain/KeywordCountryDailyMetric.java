package com.forever102.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDate;
import java.util.Objects;
import java.util.regex.Pattern;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "keyword_country_daily_metrics", uniqueConstraints = @UniqueConstraint(
        name = "uk_keyword_country_daily_metrics",
        columnNames = {"keyword_id", "metric_date", "country_code"}))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class KeywordCountryDailyMetric {

    // ISO 3166-1 alpha-2. DB 의 CHECK 과 같은 규칙이라 둘 중 하나만 고치면 안 된다.
    private static final Pattern COUNTRY_CODE = Pattern.compile("[A-Z]{2}");

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "keyword_id", nullable = false)
    private Keyword keyword;

    @Column(name = "country_code", nullable = false, length = 2)
    private String countryCode;

    // KST 기준 일자다. 파이프라인의 일 버킷이 KST 로 잘려 있다.
    @Column(name = "metric_date", nullable = false)
    private LocalDate metricDate;

    @Column(name = "mention_count", nullable = false)
    private long mentionCount;

    public KeywordCountryDailyMetric(Keyword keyword, String countryCode, LocalDate metricDate,
            long mentionCount) {
        if (countryCode == null || !COUNTRY_CODE.matcher(countryCode).matches()) {
            throw new IllegalArgumentException("국가 코드는 대문자 두 자리여야 합니다.");
        }
        if (mentionCount < 0) {
            throw new IllegalArgumentException("언급량은 0 이상이어야 합니다.");
        }
        this.keyword = Objects.requireNonNull(keyword);
        this.countryCode = countryCode;
        this.metricDate = Objects.requireNonNull(metricDate);
        this.mentionCount = mentionCount;
    }
}
