package com.forever102.member.dto;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class MemberDomainUpdateRequestTest {

    @Test
    @DisplayName("분야 코드 문자열을 enum으로 바꾼다")
    void convertsCodesToDomains() {
        // when & then
        assertThat(new MemberDomainUpdateRequest(List.of("DEVELOP", "FASHION")).toDomains())
                .containsExactly(Domain.DEVELOP, Domain.FASHION);
    }

    @Test
    @DisplayName("같은 분야를 여러 번 보내도 하나로 합친다")
    void mergesDuplicatedDomains() {
        // when & then
        assertThat(new MemberDomainUpdateRequest(List.of("DEVELOP", "DEVELOP")).toDomains())
                .containsExactly(Domain.DEVELOP);
    }

    @Test
    @DisplayName("앞뒤 공백과 소문자를 허용한다")
    void acceptsLowerCaseAndPadding() {
        // when & then
        assertThat(new MemberDomainUpdateRequest(List.of("  develop  ")).toDomains())
                .containsExactly(Domain.DEVELOP);
    }

    @Test
    @DisplayName("빈 목록은 빈 결과가 되어 개수 검증에서 걸린다")
    void convertsEmptyListToEmptyResult() {
        // when & then
        assertThat(new MemberDomainUpdateRequest(List.of()).toDomains()).isEmpty();
    }

    @Test
    @DisplayName("정의되지 않은 분야 코드는 DOMAIN_NOT_FOUND 예외가 발생한다")
    void rejectsUnknownDomain() {
        // given
        MemberDomainUpdateRequest request = new MemberDomainUpdateRequest(List.of("COOKING"));

        // when & then
        assertThatThrownBy(request::toDomains)
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.DOMAIN_NOT_FOUND);
    }

    @Test
    @DisplayName("목록에 null이 섞여 있으면 DOMAIN_NOT_FOUND 예외가 발생한다")
    void rejectsNullElement() {
        // given
        MemberDomainUpdateRequest request = new MemberDomainUpdateRequest(Arrays.asList("DEVELOP", null));

        // when & then
        assertThatThrownBy(request::toDomains)
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.DOMAIN_NOT_FOUND);
    }

    @Test
    @DisplayName("요청 순서와 무관하게 변환 자체는 실패하지 않는다")
    void keepsRequestOrderWhileConverting() {
        // when & then
        assertThat(new MemberDomainUpdateRequest(List.of("FASHION", "DEVELOP")).toDomains())
                .containsExactly(Domain.FASHION, Domain.DEVELOP);
    }
}
