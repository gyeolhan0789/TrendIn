package com.forever102.member.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.SavedTrend;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import jakarta.persistence.EntityManager;
import java.time.OffsetDateTime;
import java.util.List;
import org.hibernate.Hibernate;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.data.domain.PageRequest;

@DataJpaTest
class SavedTrendRepositoryTest {

    @Autowired SavedTrendRepository savedTrendRepository;
    @Autowired EntityManager entityManager;

    @Test
    @DisplayName("회원이 저장한 트렌드만 최신 저장순으로 키워드와 함께 조회한다")
    void findsMembersSavedTrendsInLatestOrder() {
        // given
        Member member = persistMember("member@example.com");
        Member other = persistMember("other@example.com");
        Trend firstTrend = persistTrend("Kubernetes");
        Trend secondTrend = persistTrend("AI Agent");
        SavedTrend first = savedTrendRepository.saveAndFlush(SavedTrend.save(member, firstTrend));
        SavedTrend second = savedTrendRepository.saveAndFlush(SavedTrend.save(member, secondTrend));
        savedTrendRepository.saveAndFlush(SavedTrend.save(other, firstTrend));
        entityManager.clear();

        // when
        var result = savedTrendRepository.findAllByMemberIdOrderByCreatedAtDescIdDesc(
                member.getId(), PageRequest.of(0, 20));

        // then
        assertThat(result.getContent()).extracting(SavedTrend::getId)
                .containsExactly(second.getId(), first.getId());
        assertThat(result.getContent()).allSatisfy(savedTrend -> {
            assertThat(Hibernate.isInitialized(savedTrend.getTrend())).isTrue();
            assertThat(Hibernate.isInitialized(savedTrend.getTrend().getKeyword())).isTrue();
        });
    }

    private Member persistMember(String email) {
        Member member = Member.create(email, "encoded-password", email.substring(0, 5));
        entityManager.persist(member);
        return member;
    }

    private Trend persistTrend(String keywordName) {
        Keyword keyword = new Keyword(keywordName, Domain.DEVELOP);
        entityManager.persist(keyword);
        Trend trend = new Trend(keyword, List.of(TrendType.CURRENT), "설명", null, null,
                OffsetDateTime.parse("2026-08-31T08:00:00+09:00"));
        entityManager.persist(trend);
        return trend;
    }
}
