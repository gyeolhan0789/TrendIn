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

@Entity
@Table(name = "notification_settings", uniqueConstraints = @UniqueConstraint(
        name = "uk_notification_settings_member", columnNames = "member_id"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class NotificationSetting {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
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
