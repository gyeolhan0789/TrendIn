package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willAnswer;
import static org.mockito.Mockito.never;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberDomain;
import com.forever102.member.dto.DomainResponse;
import com.forever102.member.dto.MemberDomainUpdateRequest;
import com.forever102.member.repository.MemberDomainRepository;
import com.forever102.member.repository.MemberInterestKeywordRepository;
import com.forever102.member.repository.MemberRepository;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class MemberDomainServiceTest {

    private static final Long MEMBER_ID = 1L;

    @Mock
    private MemberDomainRepository memberDomainRepository;

    @Mock
    private MemberInterestKeywordRepository interestKeywordRepository;

    @Mock
    private MemberRepository memberRepository;

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


    @Test
    @DisplayName("요청한 분야로 교체하고 교체 결과를 반환한다")
    void replacesDomains() {
        // given
        Member member = givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID))
                .willReturn(List.of(Domain.DEVELOP))
                .willReturn(List.of(Domain.DEVELOP, Domain.FASHION));

        // when
        List<DomainResponse> responses = memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP", "FASHION"));

        // then
        assertThat(responses).extracting(DomainResponse::domain)
                .containsExactly(Domain.DEVELOP, Domain.FASHION);
    }

    @Test
    @DisplayName("요청에서 빠진 분야의 관심 키워드를 같은 작업에서 지운다")
    void removesInterestKeywordsOfDroppedDomains() {
        // given
        givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(Domain.DEVELOP));

        // when
        memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP"));

        // then
        then(interestKeywordRepository).should()
                .deleteByMemberIdAndKeywordDomainNotIn(MEMBER_ID, Set.of(Domain.DEVELOP));
    }

    @Test
    @DisplayName("요청에서 빠진 분야 선택을 지운다")
    void removesDroppedDomains() {
        // given
        givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(Domain.DEVELOP));

        // when
        memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP"));

        // then
        then(memberDomainRepository).should()
                .deleteByMemberIdAndDomainNotIn(MEMBER_ID, Set.of(Domain.DEVELOP));
    }

    @Test
    @DisplayName("이미 선택한 분야는 다시 저장하지 않는다")
    void doesNotResaveAlreadySelectedDomain() {
        // given
        givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(Domain.DEVELOP));

        // when
        memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP"));

        // then
        then(memberDomainRepository).should(never()).save(any(MemberDomain.class));
    }

    @Test
    @DisplayName("새로 추가된 분야만 저장한다")
    void savesOnlyNewDomains() {
        // given
        givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID))
                .willReturn(List.of(Domain.DEVELOP))
                .willReturn(List.of(Domain.DEVELOP, Domain.FASHION));

        // when
        memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP", "FASHION"));

        // then
        ArgumentCaptor<MemberDomain> captor = ArgumentCaptor.captor();
        then(memberDomainRepository).should().save(captor.capture());
        assertThat(captor.getValue().getDomain()).isEqualTo(Domain.FASHION);
    }

    @Test
    @DisplayName("교체에 성공하면 온보딩을 완료 처리한다")
    void completesOnboardingOnSuccess() {
        // given
        Member member = givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(Domain.DEVELOP));

        // when
        memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP"));

        // then
        assertThat(member.isOnboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("영속성 컨텍스트를 비우는 삭제 쿼리보다 먼저 온보딩을 완료 처리한다")
    void completesOnboardingBeforeClearingDeletes() {
        // given
        Member member = givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(Domain.DEVELOP));
        // 삭제 쿼리는 clearAutomatically로 회원을 준영속 상태로 만든다. 그 시점의 완료 여부를 기록한다.
        List<Boolean> completedAtDelete = new ArrayList<>();
        willAnswer(invocation -> {
            completedAtDelete.add(member.isOnboardingCompleted());
            return null;
        }).given(interestKeywordRepository)
                .deleteByMemberIdAndKeywordDomainNotIn(MEMBER_ID, Set.of(Domain.DEVELOP));
        willAnswer(invocation -> {
            completedAtDelete.add(member.isOnboardingCompleted());
            return null;
        }).given(memberDomainRepository)
                .deleteByMemberIdAndDomainNotIn(MEMBER_ID, Set.of(Domain.DEVELOP));

        // when
        memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP"));

        // then
        assertThat(completedAtDelete).containsExactly(true, true);
    }

    @Test
    @DisplayName("이미 온보딩을 완료한 회원도 수정 후 완료 상태를 유지한다")
    void keepsOnboardingCompletedOnLaterUpdate() {
        // given
        Member member = givenMember();
        member.completeOnboarding();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(Domain.DEVELOP));

        // when
        memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP"));

        // then
        assertThat(member.isOnboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("분야를 하나도 보내지 않으면 INTEREST_COUNT_INVALID 예외가 발생한다")
    void rejectsEmptyDomains() {
        // when & then
        assertThatThrownBy(() -> memberDomainService.updateMyDomains(MEMBER_ID, request()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INTEREST_COUNT_INVALID);
    }

    @Test
    @DisplayName("개수 검증에 실패하면 아무것도 지우거나 저장하지 않는다")
    void doesNotTouchDataWhenCountInvalid() {
        // when
        catchThrowable(() -> memberDomainService.updateMyDomains(MEMBER_ID, request()));

        // then
        then(memberDomainRepository).shouldHaveNoInteractions();
        then(interestKeywordRepository).shouldHaveNoInteractions();
        then(memberRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("정의되지 않은 분야가 섞여 있으면 DOMAIN_NOT_FOUND 예외가 발생한다")
    void rejectsUnknownDomain() {
        // when & then
        assertThatThrownBy(() -> memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP", "COOKING")))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.DOMAIN_NOT_FOUND);
    }

    @Test
    @DisplayName("존재하지 않는 분야가 있으면 아무것도 바꾸지 않는다")
    void doesNotTouchDataWhenDomainUnknown() {
        // when
        catchThrowable(() -> memberDomainService.updateMyDomains(MEMBER_ID, request("COOKING")));

        // then
        then(memberDomainRepository).shouldHaveNoInteractions();
        then(interestKeywordRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("탈퇴 등으로 회원이 없으면 MEMBER_NOT_FOUND 예외가 발생한다")
    void rejectsMissingMember() {
        // given
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP")))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.MEMBER_NOT_FOUND);
    }

    @Test
    @DisplayName("중복으로 보낸 분야는 하나로 합쳐 교체한다")
    void mergesDuplicatedDomains() {
        // given
        givenMember();
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(Domain.DEVELOP));

        // when
        List<DomainResponse> responses =
                memberDomainService.updateMyDomains(MEMBER_ID, request("DEVELOP", "DEVELOP"));

        // then
        assertThat(responses).hasSize(1);
        then(memberDomainRepository).should()
                .deleteByMemberIdAndDomainNotIn(MEMBER_ID, Set.of(Domain.DEVELOP));
    }

    private MemberDomainUpdateRequest request(String... domains) {
        return new MemberDomainUpdateRequest(List.of(domains));
    }

    private Member givenMember() {
        Member member = Member.create("test@example.com", "{bcrypt}hash", "trenduser");
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        return member;
    }
    private void givenSelected(Domain... domains) {
        given(memberDomainRepository.findDomainsByMemberId(MEMBER_ID)).willReturn(List.of(domains));
    }
}
