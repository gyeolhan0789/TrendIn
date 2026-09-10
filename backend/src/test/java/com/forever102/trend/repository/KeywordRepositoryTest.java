package com.forever102.trend.repository;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Keyword;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;

@DataJpaTest
class KeywordRepositoryTest {

    @Autowired KeywordRepository keywordRepository;

    @Test
    @DisplayName("같은 분야에 정규화 이름이 같은 키워드는 중복 저장할 수 없다")
    void rejectsDuplicateNormalizedNameInSameDomain() {
        // given
        keywordRepository.saveAndFlush(new Keyword("AI Agent", Domain.DEVELOP));

        // when & then
        assertThatThrownBy(() -> keywordRepository.saveAndFlush(
                new Keyword("ai agent", Domain.DEVELOP)))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
