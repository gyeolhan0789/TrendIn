package com.forever102.backend.auth.domain;

import com.forever102.backend.global.entity.BaseEntity;
import com.forever102.backend.member.domain.Member;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Duration;
import java.time.OffsetDateTime;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;

@Entity
@Table(
        name = "refresh_tokens",
        indexes = @Index(name = "ix_refresh_tokens_member_id", columnList = "member_id")
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RefreshToken extends BaseEntity {

    public static final Duration EXPIRATION = Duration.ofSeconds(14 * 24 * 60 * 60L);

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
    private Member member;

    @Column(nullable = false, unique = true)
    private String tokenHash;

    @Column(nullable = false)
    private OffsetDateTime expiresAt;

    private OffsetDateTime revokedAt;

    private RefreshToken(Member member, String tokenHash, OffsetDateTime expiresAt) {
        this.member = member;
        this.tokenHash = tokenHash;
        this.expiresAt = expiresAt;
    }

    public static RefreshToken issue(Member member, String tokenHash, OffsetDateTime issuedAt) {
        return new RefreshToken(member, tokenHash, issuedAt.plus(EXPIRATION));
    }

    public void revoke(OffsetDateTime revokedAt) {
        if (isRevoked()) {
            return;
        }
        this.revokedAt = revokedAt;
    }

    public boolean isRevoked() {
        return revokedAt != null;
    }

    public boolean isExpired(OffsetDateTime at) {
        return !at.isBefore(expiresAt);
    }

    public boolean isUsable(OffsetDateTime at) {
        return !isRevoked() && !isExpired(at);
    }
}
