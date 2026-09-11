package com.forever102.member.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberDomain;
import jakarta.persistence.EntityManager;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class MemberDomainRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired MemberDomainRepository memberDomainRepository;

    @Test
    @DisplayName("회원이 선택한 분야 코드를 조회한다")
    void findsSelectedDomains() {
        // given
        Member member = persistMember("member@example.com");
        persistMemberDomain(member, Domain.DEVELOP);
        persistMemberDomain(member, Domain.FASHION);

        // when
        List<Domain> domains = memberDomainRepository.findDomainsByMemberId(member.getId());

        // then
        assertThat(domains).containsExactlyInAnyOrder(Domain.DEVELOP, Domain.FASHION);
    }

    @Test
    @DisplayName("선택한 분야가 없으면 빈 목록을 반환한다")
    void returnsEmptyListWhenNothingSelected() {
        // given
        Member member = persistMember("empty@example.com");

        // when & then
        assertThat(memberDomainRepository.findDomainsByMemberId(member.getId())).isEmpty();
    }

    @Test
    @DisplayName("다른 회원이 고른 분야는 조회되지 않는다")
    void doesNotLeakOtherMembersDomains() {
        // given
        Member owner = persistMember("owner@example.com");
        Member other = persistMember("other@example.com");
        persistMemberDomain(owner, Domain.DEVELOP);

        // when & then
        assertThat(memberDomainRepository.findDomainsByMemberId(other.getId())).isEmpty();
    }

    @Test
    @DisplayName("존재하지 않는 회원으로 조회하면 빈 목록을 반환한다")
    void returnsEmptyListForUnknownMember() {
        // when & then
        assertThat(memberDomainRepository.findDomainsByMemberId(-1L)).isEmpty();
    }

    private Member persistMember(String email) {
        Member member = Member.create(email, "password-hash", "회원");
        entityManager.persist(member);
        return member;
    }

    private void persistMemberDomain(Member member, Domain domain) {
        memberDomainRepository.saveAndFlush(MemberDomain.register(member, domain));
    }
}
