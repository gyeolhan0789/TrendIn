package com.forever102.member.domain;

import com.forever102.global.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.ColumnDefault;

@Entity
@Table(
        name = "members",
        uniqueConstraints = @UniqueConstraint(name = "uk_members_email", columnNames = "email")
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Member extends BaseEntity {

    // members는 BIGSERIAL이므로 시퀀스가 아닌 identity 컬럼에 맞춘다.
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 254)
    private String email;

    // 컬럼명은 DDL의 password를 따르되, 저장하는 값이 해시임을 드러내도록 필드명은 passwordHash로 둔다.
    // OAuth로만 가입한 회원은 비밀번호가 없어 null을 허용한다.
    @Column(name = "password", length = 255)
    private String passwordHash;

    @Column(nullable = false, length = 30)
    private String nickname;

    @Column(name = "onboarding_completed", nullable = false)
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

    /**
     * OAuth 제공자로만 가입한 회원. 비밀번호가 없어 이메일·비밀번호 로그인으로는 들어올 수 없다.
     */
    public static Member createOAuthMember(String email, String nickname) {
        return new Member(email, null, nickname);
    }

    public void updateNickname(String nickname) {
        this.nickname = nickname;
    }

    public void completeOnboarding() {
        this.onboardingCompleted = true;
    }
}
