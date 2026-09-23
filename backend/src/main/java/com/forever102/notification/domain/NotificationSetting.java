package com.forever102.notification.domain;

import com.forever102.member.domain.Member;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;

@Entity
@Table(name = "notification_settings", uniqueConstraints = @UniqueConstraint(
        name = "uk_notification_settings_member", columnNames = "member_id"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class NotificationSetting {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * 회원이 떠나면 함께 사라진다. Flyway가 만든 {@code fk_notification_settings_member}에
     * 이미 ON DELETE CASCADE가 걸려 있고, 이 선언은 그 사실을 엔티티에도 적어 둔 것이다.
     *
     * <p>운영 DDL은 Flyway가 소유하므로 이 선언이 그것을 바꾸지는 않는다. 다만
     * {@code ddl-auto}가 스키마를 만드는 시험 환경에서는 이것이 없으면 CASCADE가 빠져,
     * 운영에서는 되는 탈퇴가 시험에서만 외래키 위반으로 막힌다.
     */
    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
    private Member member;

    @Column(name = "keyword_surge_enabled", nullable = false)
    private boolean keywordSurgeEnabled = true;

    @Column(name = "keyword_drop_enabled", nullable = false)
    private boolean keywordDropEnabled = true;

    @Column(name = "new_trend_enabled", nullable = false)
    private boolean newTrendEnabled = true;

    @Column(name = "trend_turning_point_enabled", nullable = false)
    private boolean trendTurningPointEnabled = true;

    private NotificationSetting(Member member) {
        this.member = Objects.requireNonNull(member);
    }

    public static NotificationSetting defaults(Member member) {
        return new NotificationSetting(member);
    }

    public void update(boolean keywordSurgeEnabled, boolean keywordDropEnabled,
            boolean newTrendEnabled, boolean trendTurningPointEnabled) {
        this.keywordSurgeEnabled = keywordSurgeEnabled;
        this.keywordDropEnabled = keywordDropEnabled;
        this.newTrendEnabled = newTrendEnabled;
        this.trendTurningPointEnabled = trendTurningPointEnabled;
    }

    public boolean isEnabled(NotificationType type) {
        return switch (type) {
            case KEYWORD_SURGE -> keywordSurgeEnabled;
            case KEYWORD_DROP -> keywordDropEnabled;
            case NEW_TREND -> newTrendEnabled;
            case TREND_TURNING_POINT -> trendTurningPointEnabled;
            case TREND_CHANGE -> true;
        };
    }
}
