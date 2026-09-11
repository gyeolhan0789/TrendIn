package com.forever102.member.dto;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class DomainResponseTest {

    @Test
    @DisplayName("분야 코드와 표시명을 함께 담는다")
    void carriesCodeAndDisplayName() {
        // when
        DomainResponse response = DomainResponse.from(Domain.DEVELOP);

        // then
        assertThat(response).isEqualTo(new DomainResponse(Domain.DEVELOP, "개발"));
    }

    @Test
    @DisplayName("표시명은 enum이 가진 값을 그대로 쓴다")
    void usesDisplayNameFromEnum() {
        // when & then
        assertThat(DomainResponse.from(Domain.FASHION).name()).isEqualTo(Domain.FASHION.getName());
    }

    @Test
    @DisplayName("전체 목록은 정의된 분야를 하나도 빠뜨리지 않는다")
    void listsEveryDomain() {
        // when
        List<DomainResponse> responses = DomainResponse.all();

        // then
        assertThat(responses).hasSameSizeAs(Domain.values());
        assertThat(responses).extracting(DomainResponse::domain).containsExactly(Domain.values());
    }

    @Test
    @DisplayName("전체 목록은 enum 선언 순서를 유지한다")
    void keepsDeclarationOrder() {
        // when & then
        assertThat(DomainResponse.all())
                .extracting(DomainResponse::domain)
                .containsExactly(Domain.DEVELOP, Domain.FASHION);
    }
}
