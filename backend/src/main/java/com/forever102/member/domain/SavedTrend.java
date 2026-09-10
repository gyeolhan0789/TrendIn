package com.forever102.member.domain;

import com.forever102.trend.domain.Trend;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.OffsetDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(
        name = "saved_trends",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_saved_trends_member_trend",
                columnNames = {"member_id", "trend_id"})
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class SavedTrend {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "trend_id", nullable = false)
    private Trend trend;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    private SavedTrend(Member member, Trend trend) {
        this.member = Objects.requireNonNull(member);
        this.trend = Objects.requireNonNull(trend);
    }

    public static SavedTrend save(Member member, Trend trend) {
        return new SavedTrend(member, trend);
    }

    @PrePersist
    void onCreate() {
        createdAt = OffsetDateTime.now();
    }
}
