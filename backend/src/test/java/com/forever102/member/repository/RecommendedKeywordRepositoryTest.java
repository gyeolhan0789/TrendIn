package com.forever102.member.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordRelation;
import com.forever102.trend.repository.KeywordRelationRepository;
import jakarta.persistence.EntityManager;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class RecommendedKeywordRepositoryTest {

    /* 개수 말고 다른 것을 보는 시험은 상한을 걸지 않는다. 상한은 아래 전용 시험이 본다. */
    private static final Pageable UNLIMITED = Pageable.unpaged();

    @Autowired EntityManager entityManager;
    @Autowired KeywordRelationRepository keywordRelationRepository;

    @Test
    @DisplayName("회원의 관심 키워드와 연결된 키워드를 추천한다")
    void findsKeywordsRelatedToMemberInterests() {
        // given
        Member member = persistMember();
        Keyword interest = persistKeyword("Ballet Sneakers");
        Keyword recommendation = persistKeyword("Mary Jane Sneakers");
        persistInterest(member, interest);
        persistRelation(interest, recommendation, "80.00");
        flushAndClear();

        // when
        var result = keywordRelationRepository.findRecommendedKeywords(member.getId(), UNLIMITED);

        // then
        assertThat(result).singleElement()
                .extracting(it -> it.getKeywordId(), it -> it.getKeyword())
                .containsExactly(recommendation.getId(), "Mary Jane Sneakers");
    }

    @Test
    @DisplayName("이미 관심 키워드로 등록한 키워드는 추천에서 제외한다")
    void excludesRegisteredInterestKeywords() {
        // given
        Member member = persistMember();
        Keyword firstInterest = persistKeyword("Ballet Sneakers");
        Keyword secondInterest = persistKeyword("Mary Jane Sneakers");
        persistInterest(member, firstInterest);
        persistInterest(member, secondInterest);
        persistRelation(firstInterest, secondInterest, "90.00");
        flushAndClear();

        // when
        var result = keywordRelationRepository.findRecommendedKeywords(member.getId(), UNLIMITED);

        // then
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("여러 관심 키워드가 같은 키워드를 추천하면 가장 높은 연관도만 사용한다")
    void usesHighestRelationScoreForDuplicateRecommendation() {
        // given
        Member member = persistMember();
        Keyword firstInterest = persistKeyword("Ballet Sneakers");
        Keyword secondInterest = persistKeyword("Retro Sneakers");
        Keyword recommendation = persistKeyword("Mary Jane Sneakers");
        persistInterest(member, firstInterest);
        persistInterest(member, secondInterest);
        persistRelation(firstInterest, recommendation, "70.00");
        persistRelation(secondInterest, recommendation, "92.50");
        flushAndClear();

        // when
        var result = keywordRelationRepository.findRecommendedKeywords(member.getId(), UNLIMITED);

        // then
        assertThat(result).singleElement()
                .extracting(it -> it.getRelationScore())
                .isEqualTo(new BigDecimal("92.50"));
    }

    @Test
    @DisplayName("추천 키워드는 연관도 내림차순과 키워드 ID 오름차순으로 정렬한다")
    void sortsByRelationScoreAndKeywordId() {
        // given
        Member member = persistMember();
        Keyword interest = persistKeyword("Ballet Sneakers");
        Keyword first = persistKeyword("First");
        Keyword second = persistKeyword("Second");
        Keyword highest = persistKeyword("Highest");
        persistInterest(member, interest);
        persistRelation(interest, second, "80.00");
        persistRelation(interest, first, "80.00");
        persistRelation(interest, highest, "95.00");
        flushAndClear();

        // when
        var result = keywordRelationRepository.findRecommendedKeywords(member.getId(), UNLIMITED);

        // then
        assertThat(result).extracting(it -> it.getKeywordId())
                .containsExactly(highest.getId(), first.getId(), second.getId());
    }

    @Test
    @DisplayName("상한을 주면 연관도 높은 쪽부터 그 개수까지만 가져온다")
    void limitsToTopScoredRecommendations() {
        /*
         * 상한이 없으면 이 질의는 열려 있다 — 후보가 내 관심 키워드에 연결된
         * keyword_relations 전부라, 관심 키워드를 많이 등록한 회원일수록 행이 불어난다.
         * 화면에서 자르는 것으로는 DB 비용과 전송량이 줄지 않는다.
         *
         * 개수만 보지 않고 **어느 것이 남는지**까지 본다. 상한이 정렬 뒤에 걸려야
         * "상위 N개" 이고, 정렬 전에 걸리면 아무 N개가 된다.
         */
        // given
        Member member = persistMember();
        Keyword interest = persistKeyword("Ballet Sneakers");
        Keyword low = persistKeyword("Low");
        Keyword middle = persistKeyword("Middle");
        Keyword highest = persistKeyword("Highest");
        persistInterest(member, interest);
        persistRelation(interest, low, "10.00");
        persistRelation(interest, middle, "50.00");
        persistRelation(interest, highest, "90.00");
        flushAndClear();

        // when
        var result = keywordRelationRepository.findRecommendedKeywords(
                member.getId(), PageRequest.of(0, 2));

        // then
        assertThat(result).extracting(it -> it.getKeywordId())
                .containsExactly(highest.getId(), middle.getId());
    }

    private Member persistMember() {
        Member member = Member.create("member@example.com", "password-hash", "회원");
        entityManager.persist(member);
        return member;
    }

    private Keyword persistKeyword(String name) {
        Keyword keyword = new Keyword(name, Domain.FASHION);
        entityManager.persist(keyword);
        return keyword;
    }

    private void persistInterest(Member member, Keyword keyword) {
        entityManager.persist(MemberInterestKeyword.register(member, keyword));
    }

    private void persistRelation(Keyword source, Keyword target, String score) {
        entityManager.persist(new KeywordRelation(source, target, new BigDecimal(score), 10,
                OffsetDateTime.parse("2026-08-31T08:00:00+09:00")));
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
