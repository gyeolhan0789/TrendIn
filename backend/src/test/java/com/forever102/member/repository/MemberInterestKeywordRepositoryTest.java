package com.forever102.member.repository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.trend.domain.Keyword;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class MemberInterestKeywordRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired MemberInterestKeywordRepository interestKeywordRepository;

    @Test
    @DisplayName("회원과 키워드 조합으로 관심 키워드 등록 여부를 조회한다")
    void findsRegistrationByMemberAndKeyword() {
        // given
        Member member = persistMember();
        Keyword keyword = persistKeyword();
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(member, keyword));

        // when
        boolean exists = interestKeywordRepository.existsByMemberIdAndKeywordId(member.getId(), keyword.getId());

        // then
        assertThat(exists).isTrue();
    }

    @Test
    @DisplayName("같은 회원은 동일한 키워드를 두 번 등록할 수 없다")
    void preventsDuplicateRegistration() {
        // given
        Member member = persistMember();
        Keyword keyword = persistKeyword();
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(member, keyword));

        // when & then
        assertThatThrownBy(() -> interestKeywordRepository.saveAndFlush(
                MemberInterestKeyword.register(member, keyword)))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("회원의 관심 키워드를 등록 순서대로 함께 조회한다")
    void findsMemberInterestKeywordsWithKeywords() {
        // given
        Member member = persistMember();
        Keyword first = persistKeyword("Kubernetes", Domain.DEVELOP);
        Keyword second = persistKeyword("Ballet Sneakers", Domain.FASHION);
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(member, first));
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(member, second));
        entityManager.clear();

        // when
        var result = interestKeywordRepository.findAllByMemberIdOrderByIdAsc(member.getId());

        // then
        assertThat(result).extracting(interest -> interest.getKeyword().getName())
                .containsExactly("Kubernetes", "Ballet Sneakers");
    }

    @Test
    @DisplayName("회원과 분야가 모두 일치하는 관심 키워드만 조회한다")
    void findsMemberInterestKeywordsByDomain() {
        // given
        Member member = persistMember();
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(
                member, persistKeyword("Kubernetes", Domain.DEVELOP)));
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(
                member, persistKeyword("Ballet Sneakers", Domain.FASHION)));
        entityManager.clear();

        // when
        var result = interestKeywordRepository
                .findAllByMemberIdAndKeywordDomainOrderByIdAsc(member.getId(), Domain.DEVELOP);

        // then
        assertThat(result).extracting(interest -> interest.getKeyword().getName())
                .containsExactly("Kubernetes");
    }

    @Test
    @DisplayName("다른 회원이 등록한 관심 키워드는 소유권 조회에서 제외한다")
    void excludesOtherMembersInterestKeyword() {
        // given
        Member owner = persistMember();
        Member other = Member.create("other@example.com", "password-hash", "다른 회원");
        entityManager.persist(other);
        MemberInterestKeyword interestKeyword = interestKeywordRepository.saveAndFlush(
                MemberInterestKeyword.register(owner, persistKeyword()));

        // when
        var result = interestKeywordRepository.findByIdAndMemberId(
                interestKeyword.getId(), other.getId());

        // then
        assertThat(result).isEmpty();
    }


    @Test
    @DisplayName("남길 분야에 속하지 않는 관심 키워드만 지운다")
    void deletesInterestKeywordsOutsideKeptDomains() {
        // given
        Member member = persistMember();
        Keyword fashionKeyword = persistKeyword("Ballet Sneakers", Domain.FASHION);
        Keyword developKeyword = persistKeyword("Spring Boot", Domain.DEVELOP);
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(member, fashionKeyword));
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(member, developKeyword));

        // when
        interestKeywordRepository.deleteByMemberIdAndKeywordDomainNotIn(
                member.getId(), java.util.List.of(Domain.DEVELOP));

        // then
        assertThat(interestKeywordRepository.findAllByMemberIdOrderByIdAsc(member.getId()))
                .extracting(interestKeyword -> interestKeyword.getKeyword().getDomain())
                .containsExactly(Domain.DEVELOP);
    }

    @Test
    @DisplayName("다른 회원의 관심 키워드는 지우지 않는다")
    void doesNotDeleteOtherMembersInterestKeywords() {
        // given
        Member owner = persistMember();
        Member other = persistMember("other-ik@example.com");
        Keyword fashionKeyword = persistKeyword("Ballet Sneakers", Domain.FASHION);
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(owner, fashionKeyword));
        interestKeywordRepository.saveAndFlush(MemberInterestKeyword.register(other, fashionKeyword));

        // when
        interestKeywordRepository.deleteByMemberIdAndKeywordDomainNotIn(
                owner.getId(), java.util.List.of(Domain.DEVELOP));

        // then
        assertThat(interestKeywordRepository.findAllByMemberIdOrderByIdAsc(owner.getId())).isEmpty();
        assertThat(interestKeywordRepository.findAllByMemberIdOrderByIdAsc(other.getId())).hasSize(1);
    }

    private Member persistMember() {
        return persistMember("member@example.com");
    }

    private Member persistMember(String email) {
        Member member = Member.create(email, "password-hash", "회원");
        entityManager.persist(member);
        return member;
    }

    private Keyword persistKeyword() {
        return persistKeyword("Ballet Sneakers", Domain.FASHION);
    }

    private Keyword persistKeyword(String name, Domain domain) {
        Keyword keyword = new Keyword(name, domain);
        entityManager.persist(keyword);
        return keyword;
    }
}
