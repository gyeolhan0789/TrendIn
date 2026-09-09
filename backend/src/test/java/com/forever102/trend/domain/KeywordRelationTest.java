package com.forever102.trend.domain;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.member.domain.Domain;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class KeywordRelationTest {

    @ParameterizedTest
    @ValueSource(strings = {"-0.01", "100.01"})
    @DisplayName("0~100 범위를 벗어난 관계 점수를 거부한다")
    void rejectsOutOfRangeScore(String score) {
        // given
        Keyword source = new Keyword("Ballet Sneakers", Domain.FASHION);
        Keyword target = new Keyword("Mary Jane Sneakers", Domain.FASHION);

        // when & then
        assertThatThrownBy(() -> new KeywordRelation(source, target, new BigDecimal(score), 1,
                OffsetDateTime.parse("2026-08-31T08:00:00+09:00")))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
