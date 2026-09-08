package com.forever102.member.domain;

import com.forever102.global.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Enumerated;
import jakarta.persistence.EnumType;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;

@Entity
@Table(
        name = "member_domains",
        uniqueConstraints = @UniqueConstraint(
                name = "ux_member_domains_member_id_domain",
                columnNames = {"member_id", "domain"}
        )
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MemberDomain extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id", nullable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
    private Member member;

    @Enumerated(EnumType.STRING)
    @Column(name = "domain", nullable = false)
    private Domain domain;

    private MemberDomain(Member member, Domain domain) {
        this.member = member;
        this.domain = domain;
    }

    public static MemberDomain register(Member member, Domain domain) {
        return new MemberDomain(member, domain);
    }
}
