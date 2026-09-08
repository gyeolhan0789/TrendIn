package com.forever102.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "trends")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Trend {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "keyword_id", nullable = false)
    private Keyword keyword;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Enumerated(EnumType.STRING)
    @Column(name = "trend_types", nullable = false)
    private TrendType[] trendTypes;

    @Column(nullable = false, length = 255)
    private String description;

    @Column(columnDefinition = "text")
    private String summary;

    @Column(columnDefinition = "text")
    private String reason;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    public Trend(Keyword keyword, List<TrendType> trendTypes, String description,
            String summary, String reason, OffsetDateTime updatedAt) {
        this.keyword = Objects.requireNonNull(keyword);
        if (trendTypes == null || trendTypes.isEmpty()) {
            throw new IllegalArgumentException("트렌드 유형은 하나 이상이어야 합니다.");
        }
        this.trendTypes = trendTypes.toArray(TrendType[]::new);
        this.description = Objects.requireNonNull(description);
        this.summary = summary;
        this.reason = reason;
        this.updatedAt = Objects.requireNonNull(updatedAt);
    }

    public List<TrendType> getTrendTypes() {
        return List.copyOf(Arrays.asList(trendTypes));
    }
}
