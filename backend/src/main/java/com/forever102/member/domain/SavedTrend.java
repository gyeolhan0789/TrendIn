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
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;

@Entity
@Table(
        name = "saved_trends",
        uniqueConstraints = @UniqueConstraint(
                name = SavedTrend.UNIQUE_MEMBER_TREND_CONSTRAINT,
                columnNames = {"member_id", "trend_id"})
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class SavedTrend {

    public static final String UNIQUE_MEMBER_TREND_CONSTRAINT =
            "uk_saved_trends_member_trend";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * 회원이 떠나면 함께 사라진다. Flyway가 만든 {@code fk_saved_trends_member}에 이미
     * ON DELETE CASCADE가 걸려 있고, 이 선언은 그 사실을 엔티티에도 적어 둔 것이다.
     *
     * <p>운영 DDL은 Flyway가 소유하므로 이 선언이 그것을 바꾸지는 않는다. 다만
     * {@code ddl-auto}가 스키마를 만드는 시험 환경에서는 이것이 없으면 CASCADE가 빠져,
     * 운영에서는 되는 탈퇴가 시험에서만 외래키 위반으로 막힌다.
     */
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
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
