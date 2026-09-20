package com.forever102.member.domain;

import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.TrendType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.ColumnDefault;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(
        name = "member_interest_keywords",
        uniqueConstraints = @UniqueConstraint(
                name = MemberInterestKeyword.UNIQUE_MEMBER_KEYWORD_CONSTRAINT,
                columnNames = {"member_id", "keyword_id"})
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MemberInterestKeyword {

    public static final String UNIQUE_MEMBER_KEYWORD_CONSTRAINT =
            "uk_member_interest_keywords_member_keyword";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    @ManyToOne(optional = false)
    @JoinColumn(name = "keyword_id", nullable = false)
    private Keyword keyword;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "was_trending", nullable = false)
    @ColumnDefault("false")
    private boolean wasTrending;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Enumerated(EnumType.STRING)
    @Column(name = "previous_trend_types")
    private TrendType[] previousTrendTypes;

    private MemberInterestKeyword(Member member, Keyword keyword) {
        this.member = Objects.requireNonNull(member);
        this.keyword = Objects.requireNonNull(keyword);
        this.wasTrending = false;
        this.previousTrendTypes = new TrendType[0];
    }

    public static MemberInterestKeyword register(Member member, Keyword keyword) {
        return new MemberInterestKeyword(member, keyword);
    }

    public void updateTrendingState(boolean trending) {
        this.wasTrending = trending;
    }

    public boolean hasPreviousTrendState() {
        return previousTrendTypes != null;
    }

    public List<TrendType> getPreviousTrendTypes() {
        return previousTrendTypes == null
                ? List.of() : List.copyOf(Arrays.asList(previousTrendTypes));
    }

    public void updateTrendState(List<TrendType> trendTypes) {
        previousTrendTypes = trendTypes.toArray(TrendType[]::new);
        wasTrending = !trendTypes.isEmpty();
    }

    @PrePersist
    void onCreate() {
        createdAt = OffsetDateTime.now();
    }
}
