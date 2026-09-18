package com.forever102.member.domain;

import com.forever102.auth.domain.OAuthProvider;
import com.forever102.global.entity.BaseEntity;
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
import jakarta.persistence.UniqueConstraint;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;

/**
 * 회원과 외부 제공자 계정의 연결.
 * 같은 제공자에서 다시 로그인하면 이 연결을 통해 같은 회원을 찾는다.
 */
@Entity
@Table(
        name = "member_oauth_accounts",
        uniqueConstraints = {
                @UniqueConstraint(
                        name = "uk_member_oauth_accounts_provider_user",
                        columnNames = {"provider", "provider_user_id"}),
                @UniqueConstraint(
                        name = "uk_member_oauth_accounts_member_provider",
                        columnNames = {"member_id", "provider"})
        }
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MemberOAuthAccount extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
    private Member member;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private OAuthProvider provider;

    /** 제공자가 발급한 불변 식별자. 이메일은 바뀔 수 있어 연결 기준으로 쓰지 않는다. */
    @Column(name = "provider_user_id", nullable = false, length = 255)
    private String providerUserId;

    private MemberOAuthAccount(Member member, OAuthProvider provider, String providerUserId) {
        this.member = Objects.requireNonNull(member);
        this.provider = Objects.requireNonNull(provider);
        this.providerUserId = Objects.requireNonNull(providerUserId);
    }

    public static MemberOAuthAccount link(Member member, OAuthProvider provider, String providerUserId) {
        return new MemberOAuthAccount(member, provider, providerUserId);
    }
}
