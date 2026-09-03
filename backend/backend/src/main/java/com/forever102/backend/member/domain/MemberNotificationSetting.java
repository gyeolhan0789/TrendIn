package com.forever102.backend.member.domain;

import com.forever102.backend.global.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.MapsId;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.ColumnDefault;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;

@Entity
@Table(
        name = "member_notification_settings"
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MemberNotificationSetting extends BaseEntity {

    @Id
    private Long memberId;

    @MapsId
    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id")
    @OnDelete(action = OnDeleteAction.CASCADE)
    private Member member;

    @Column(nullable = false)
    @ColumnDefault("true")
    private boolean newTrendEnabled;

    @Column(nullable = false)
    @ColumnDefault("true")
    private boolean risingTrendEnabled;

    private MemberNotificationSetting(Member member, boolean newTrendEnabled, boolean risingTrendEnabled) {
        this.member = member;
        this.newTrendEnabled = newTrendEnabled;
        this.risingTrendEnabled = risingTrendEnabled;
    }

    public static MemberNotificationSetting createDefault(Member member) {
        return new MemberNotificationSetting(member, true, true);
    }

    public void updateSettings(boolean newTrendEnabled, boolean risingTrendEnabled) {
        this.newTrendEnabled = newTrendEnabled;
        this.risingTrendEnabled = risingTrendEnabled;
    }
}
