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

    private Member persistMember() {
        Member member = Member.create("member@example.com", "password-hash", "회원");
        entityManager.persist(member);
        return member;
    }

    private Keyword persistKeyword() {
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        entityManager.persist(keyword);
        return keyword;
    }
}
