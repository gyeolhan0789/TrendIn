package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

import com.forever102.member.domain.Domain;
import com.forever102.member.dto.DomainResponse;
import com.forever102.member.repository.MemberDomainRepository;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class MemberDomainServiceTest {

    private static final Long MEMBER_ID = 1L;

    @Mock
    private MemberDomainRepository memberDomainRepository;

    @InjectMocks
    private MemberDomainService memberDomainService;

    @Test
    @DisplayName("선택한 분야를 코드와 표시명으로 반환한다")
    void returnsSelectedDomains() {
        // given
        givenSelected(Domain.DEVELOP);

        // when
        List<DomainResponse> responses = memberDomainService.getMyDomains(MEMBER_ID);

        // then
        assertThat(responses).containsExactly(new DomainResponse(Domain.DEVELOP, "개발"));
    }

    @Test
    @DisplayName("아직 분야를 고르지 않았으면 빈 목록을 반환한다")
    void returnsEmptyListBeforeFirstRegistration() {
        // given
        givenSelected();

        // when & then
        assertThat(memberDomainService.getMyDomains(MEMBER_ID)).isEmpty();
    }

    @Test
    @DisplayName("저장 순서와 무관하게 enum 선언 순서로 정렬한다")
    void sortsByDeclarationOrder() {
        // given
        givenSelected(Domain.FASHION, Domain.DEVELOP);

        // when
        List<DomainResponse> responses = memberDomainService.getMyDomains(MEMBER_ID);

        // then
        assertThat(responses)
                .extracting(DomainResponse::domain)
                .containsExactly(Domain.DEVELOP, Domain.FASHION);
    }

    @Test
    @DisplayName("선택한 분야를 모두 반환한다")
    void returnsEverySelectedDomain() {
        // given
        givenSelected(Domain.DEVELOP, Domain.FASHION);

        // when & then
        assertThat(memberDomainService.getMyDomains(MEMBER_ID)).hasSize(2);
    }

    @Test
    @DisplayName("본인의 회원 식별자로 조회한다")
    void queriesByAuthenticatedMemberId() {
        // given
        givenSelected(Domain.DEVELOP);

        // when
        memberDomainService.getMyDomains(MEMBER_ID);

        // then
        org.mockito.BDDMockito.then(memberDomainRepository).should().findDomainsByMemberId(MEMBER_ID);
    }

    private void givenSelected(Domain... domains) {
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(domains));
    }
}
