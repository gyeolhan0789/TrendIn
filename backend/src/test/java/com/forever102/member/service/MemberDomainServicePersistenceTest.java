package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.dto.MemberDomainUpdateRequest;
import com.forever102.member.repository.MemberDomainRepository;
import com.forever102.member.repository.MemberRepository;
import jakarta.persistence.EntityManager;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;

/**
 * 관심 분야 교체를 H2와 실제 영속성 컨텍스트에서 검증한다.
 *
 * <p>단위 테스트는 리포지토리를 대역으로 바꾸므로 {@code clearAutomatically}가 영속성 컨텍스트를
 * 비우지 않는다. 그래서 회원이 준영속 상태가 되어 온보딩 완료가 DB에 반영되지 않는 문제를 잡지 못한다.
 * 여기서는 flush·clear 후 다시 읽어 DB에 실제로 남은 값을 확인한다.
 */
@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
@Import(MemberDomainService.class)
class MemberDomainServicePersistenceTest {

    @Autowired EntityManager entityManager;
    @Autowired MemberRepository memberRepository;
    @Autowired MemberDomainRepository memberDomainRepository;
    @Autowired MemberDomainService memberDomainService;

    @Test
    @DisplayName("교체에 성공하면 온보딩 완료 상태가 DB에 반영된다")
    void persistsOnboardingCompleted() {
        // given
        Member member = persistMember("onboarding@example.com");

        // when
        memberDomainService.updateMyDomains(member.getId(), request("DEVELOP"));

        // then
        assertThat(reload(member).isOnboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("분야를 다시 교체해도 온보딩 완료 상태가 DB에 남는다")
    void keepsOnboardingCompletedAfterLaterUpdate() {
        // given
        Member member = persistMember("recheck@example.com");
        memberDomainService.updateMyDomains(member.getId(), request("DEVELOP", "FASHION"));

        // when
        memberDomainService.updateMyDomains(member.getId(), request("FASHION"));

        // then
        assertThat(reload(member).isOnboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("요청한 분야만 DB에 남는다")
    void replacesDomainsInDatabase() {
        // given
        Member member = persistMember("replace@example.com");
        memberDomainService.updateMyDomains(member.getId(), request("DEVELOP", "FASHION"));

        // when
        memberDomainService.updateMyDomains(member.getId(), request("FASHION"));

        // then
        flushAndClear();
        assertThat(memberDomainRepository.findDomainsByMemberId(member.getId()))
                .containsExactly(Domain.FASHION);
    }

    private MemberDomainUpdateRequest request(String... domains) {
        return new MemberDomainUpdateRequest(List.of(domains));
    }

    private Member persistMember(String email) {
        Member member = memberRepository.save(Member.create(email, "password-hash", "회원"));
        flushAndClear();
        return member;
    }

    /** 준영속 상태에서 잃어버린 변경을 잡아내려면 DB에서 다시 읽어야 한다. */
    private Member reload(Member member) {
        flushAndClear();
        return memberRepository.findById(member.getId()).orElseThrow();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
