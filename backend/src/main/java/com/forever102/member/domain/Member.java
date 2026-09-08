package com.forever102.member.domain;

import com.forever102.global.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.ColumnDefault;

@Entity
@Table(
        name = "members"
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Member extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Long id;

    @Column(nullable = false, unique = true)
    private String email;

    private String passwordHash;

    @Column(nullable = false)
    private String nickname;

    @Column(nullable = false)
    @ColumnDefault("false")
    private boolean onboardingCompleted;

    private Member(String email, String passwordHash, String nickname) {
        this.email = email;
        this.passwordHash = passwordHash;
        this.nickname = nickname;
        this.onboardingCompleted = false;
    }

    public static Member create(String email, String passwordHash, String nickname) {
        return new Member(email, passwordHash, nickname);
    }

    public void updateNickname(String nickname) {
        this.nickname = nickname;
    }

    public void completeOnboarding() {
        this.onboardingCompleted = true;
    }
}
