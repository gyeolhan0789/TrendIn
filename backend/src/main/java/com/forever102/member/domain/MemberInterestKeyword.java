package com.forever102.member.domain;

import com.forever102.trend.domain.Keyword;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
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
        name = "member_interest_keywords",
        uniqueConstraints = @UniqueConstraint(
                name = MemberInterestKeyword.UNIQUE_MEMBER_KEYWORD_CONSTRAINT,
                columnNames = {"member_id", "keyword_id"})
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MemberInterestKeyword {

    public static final String UNIQUE_MEMBER_KEYWORD_CONSTRAINT =
            "uk_member_interest_keywords_member_keyword";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    @ManyToOne(optional = false)
    @JoinColumn(name = "keyword_id", nullable = false)
    private Keyword keyword;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    private MemberInterestKeyword(Member member, Keyword keyword) {
        this.member = Objects.requireNonNull(member);
        this.keyword = Objects.requireNonNull(keyword);
    }

    public static MemberInterestKeyword register(Member member, Keyword keyword) {
        return new MemberInterestKeyword(member, keyword);
    }

    @PrePersist
    void onCreate() {
        createdAt = OffsetDateTime.now();
    }
}
