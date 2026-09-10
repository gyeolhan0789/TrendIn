package com.forever102.notification.domain;

import com.forever102.member.domain.Member;
import com.forever102.trend.domain.Trend;
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
        name = "notifications",
        uniqueConstraints = @UniqueConstraint(
                name = Notification.UNIQUE_DEDUP_KEY_CONSTRAINT,
                columnNames = "dedup_key")
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Notification {

    public static final String UNIQUE_DEDUP_KEY_CONSTRAINT = "uk_notifications_dedup_key";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "trend_id", nullable = false)
    private Trend trend;

    @Enumerated(EnumType.STRING)
    @Column(name = "notification_type", nullable = false, length = 30)
    private NotificationType notificationType;

    @Column(nullable = false, length = 255)
    private String message;

    @Column(name = "is_read", nullable = false)
    private boolean read;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "dedup_key", nullable = false, unique = true, length = 255)
    private String dedupKey;

    private Notification(Member member, Trend trend, String message, String dedupKey) {
        this.member = Objects.requireNonNull(member);
        this.trend = Objects.requireNonNull(trend);
        this.notificationType = NotificationType.TREND_CHANGE;
        this.message = Objects.requireNonNull(message);
        this.dedupKey = Objects.requireNonNull(dedupKey);
    }

    public static Notification trendChange(
            Member member, Trend trend, String message, String dedupKey) {
        return new Notification(member, trend, message, dedupKey);
    }

    @PrePersist
    void onCreate() {
        read = false;
        createdAt = OffsetDateTime.now();
    }
}
