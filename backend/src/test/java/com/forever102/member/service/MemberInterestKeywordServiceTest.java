package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willAnswer;
import static org.mockito.Mockito.never;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.member.dto.InterestKeywordRegisterRequest;
import com.forever102.member.repository.MemberInterestKeywordRepository;
import com.forever102.member.repository.MemberRepository;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.repository.KeywordRepository;
import com.forever102.trend.repository.KeywordRelationRepository;
import com.forever102.trend.repository.KeywordRelationRepository.RecommendedKeywordProjection;
import java.math.BigDecimal;
import java.sql.SQLException;
import java.util.Optional;
import java.util.List;
import org.hibernate.exception.ConstraintViolationException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class MemberInterestKeywordServiceTest {

    private static final Long MEMBER_ID = 1L;
    private static final Long KEYWORD_ID = 81L;

    @Mock MemberRepository memberRepository;
    @Mock KeywordRepository keywordRepository;
    @Mock MemberInterestKeywordRepository interestKeywordRepository;
    @Mock KeywordRelationRepository keywordRelationRepository;
    @InjectMocks MemberInterestKeywordService interestKeywordService;

    @Test
    @DisplayName("로그인 회원이 존재하는 키워드를 관심 키워드로 등록한다")
    void registersInterestKeyword() {
        // given
        Member member = Member.create("member@example.com", "password-hash", "회원");
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        ReflectionTestUtils.setField(keyword, "id", KEYWORD_ID);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        given(keywordRepository.findById(KEYWORD_ID)).willReturn(Optional.of(keyword));
        willAnswer(invocation -> {
            MemberInterestKeyword saved = invocation.getArgument(0);
            ReflectionTestUtils.setField(saved, "id", 10L);
            return saved;
        }).given(interestKeywordRepository).saveAndFlush(any(MemberInterestKeyword.class));

        // when
        var response = interestKeywordService.register(MEMBER_ID, new InterestKeywordRegisterRequest(KEYWORD_ID));

        // then
        assertThat(response.interestKeywordId()).isEqualTo(10L);
        assertThat(response.keywordId()).isEqualTo(KEYWORD_ID);
        assertThat(response.keyword()).isEqualTo("Ballet Sneakers");
    }

    @Test
    @DisplayName("같은 키워드가 이미 등록되어 있으면 중복 등록 예외가 발생한다")
    void rejectsDuplicateInterestKeyword() {
        // given
        given(interestKeywordRepository.existsByMemberIdAndKeywordId(MEMBER_ID, KEYWORD_ID)).willReturn(true);

        // when & then
        assertThatThrownBy(() -> interestKeywordService.register(
                MEMBER_ID, new InterestKeywordRegisterRequest(KEYWORD_ID)))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INTEREST_KEYWORD_ALREADY_EXISTS);
        then(interestKeywordRepository).should(never()).saveAndFlush(any());
    }

    @Test
    @DisplayName("존재하지 않는 키워드를 등록하면 키워드 없음 예외가 발생한다")
    void rejectsUnknownKeyword() {
        // given
        Member member = Member.create("member@example.com", "password-hash", "회원");
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        given(keywordRepository.findById(KEYWORD_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> interestKeywordService.register(
                MEMBER_ID, new InterestKeywordRegisterRequest(KEYWORD_ID)))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.KEYWORD_NOT_FOUND);
    }

    @Test
    @DisplayName("동시 등록으로 유니크 제약을 위반하면 중복 등록 예외가 발생한다")
    void translatesUniqueConstraintViolation() {
        // given
        Member member = Member.create("member@example.com", "password-hash", "회원");
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        given(keywordRepository.findById(KEYWORD_ID)).willReturn(Optional.of(keyword));
        given(interestKeywordRepository.saveAndFlush(any(MemberInterestKeyword.class)))
                .willThrow(uniqueConstraintViolation());

        // when & then
        assertThatThrownBy(() -> interestKeywordService.register(
                MEMBER_ID, new InterestKeywordRegisterRequest(KEYWORD_ID)))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INTEREST_KEYWORD_ALREADY_EXISTS);
    }

    @Test
    @DisplayName("다른 DB 무결성 제약을 위반하면 중복 등록 예외로 변환하지 않는다")
    void doesNotTranslateOtherIntegrityViolation() {
        // given
        Member member = Member.create("member@example.com", "password-hash", "회원");
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        given(keywordRepository.findById(KEYWORD_ID)).willReturn(Optional.of(keyword));
        DataIntegrityViolationException violation = new DataIntegrityViolationException(
                "foreign key violation",
                new ConstraintViolationException("foreign key violation", new SQLException(), "fk_keyword"));
        given(interestKeywordRepository.saveAndFlush(any(MemberInterestKeyword.class)))
                .willThrow(violation);

        // when & then
        assertThatThrownBy(() -> interestKeywordService.register(
                MEMBER_ID, new InterestKeywordRegisterRequest(KEYWORD_ID)))
                .isSameAs(violation);
    }

    @Test
    @DisplayName("관심 키워드와 연관된 추천 키워드를 응답으로 변환한다")
    void getsRecommendedKeywords() {
        // given
        RecommendedKeywordProjection projection = org.mockito.Mockito.mock(RecommendedKeywordProjection.class);
        given(projection.getKeywordId()).willReturn(82L);
        given(projection.getKeyword()).willReturn("Mary Jane Sneakers");
        given(projection.getDomain()).willReturn(Domain.FASHION);
        given(projection.getRelationScore()).willReturn(new BigDecimal("91.50"));
        given(keywordRelationRepository.findRecommendedKeywords(MEMBER_ID)).willReturn(java.util.List.of(projection));

        // when
        var result = interestKeywordService.getRecommendedKeywords(MEMBER_ID);

        // then
        assertThat(result).singleElement().satisfies(keyword -> {
            assertThat(keyword.keywordId()).isEqualTo(82L);
            assertThat(keyword.keyword()).isEqualTo("Mary Jane Sneakers");
            assertThat(keyword.domain().code()).isEqualTo(Domain.FASHION);
            assertThat(keyword.relationScore()).isEqualByComparingTo("91.50");
        });
    }

    @Test
    @DisplayName("추천할 키워드가 없으면 빈 목록을 반환한다")
    void returnsEmptyRecommendedKeywords() {
        // given
        given(keywordRelationRepository.findRecommendedKeywords(MEMBER_ID)).willReturn(java.util.List.of());

        // when
        var result = interestKeywordService.getRecommendedKeywords(MEMBER_ID);

        // then
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("로그인 회원의 관심 키워드를 응답으로 변환한다")
    void getsInterestKeywords() {
        // given
        Member member = Member.create("member@example.com", "password-hash", "회원");
        Keyword keyword = new Keyword("Kubernetes", Domain.DEVELOP);
        MemberInterestKeyword interestKeyword = MemberInterestKeyword.register(member, keyword);
        ReflectionTestUtils.setField(interestKeyword, "id", 15L);
        ReflectionTestUtils.setField(keyword, "id", 50L);
        given(interestKeywordRepository.findAllByMemberIdOrderByIdAsc(MEMBER_ID))
                .willReturn(List.of(interestKeyword));

        // when
        var result = interestKeywordService.getInterestKeywords(MEMBER_ID, null);

        // then
        assertThat(result).singleElement().satisfies(response -> {
            assertThat(response.interestKeywordId()).isEqualTo(15L);
            assertThat(response.keywordId()).isEqualTo(50L);
            assertThat(response.keyword()).isEqualTo("Kubernetes");
            assertThat(response.domain()).isEqualTo(Domain.DEVELOP);
        });
    }

    @Test
    @DisplayName("분야를 지정하면 해당 분야의 관심 키워드를 조회한다")
    void getsInterestKeywordsByDomain() {
        // given
        given(interestKeywordRepository.findAllByMemberIdAndKeywordDomainOrderByIdAsc(
                MEMBER_ID, Domain.FASHION)).willReturn(List.of());

        // when
        interestKeywordService.getInterestKeywords(MEMBER_ID, Domain.FASHION);

        // then
        then(interestKeywordRepository).should()
                .findAllByMemberIdAndKeywordDomainOrderByIdAsc(MEMBER_ID, Domain.FASHION);
        then(interestKeywordRepository).should(never()).findAllByMemberIdOrderByIdAsc(MEMBER_ID);
    }

    @Test
    @DisplayName("로그인 회원이 소유한 관심 키워드를 삭제한다")
    void deletesOwnedInterestKeyword() {
        // given
        MemberInterestKeyword interestKeyword = MemberInterestKeyword.register(
                Member.create("member@example.com", "password-hash", "회원"),
                new Keyword("Kubernetes", Domain.DEVELOP));
        given(interestKeywordRepository.findByIdAndMemberId(15L, MEMBER_ID))
                .willReturn(Optional.of(interestKeyword));

        // when
        interestKeywordService.delete(MEMBER_ID, 15L);

        // then
        then(interestKeywordRepository).should().delete(interestKeyword);
    }

    @Test
    @DisplayName("본인 소유가 아닌 관심 키워드는 찾을 수 없음 예외가 발생한다")
    void rejectsInterestKeywordNotOwnedByMember() {
        // given
        given(interestKeywordRepository.findByIdAndMemberId(15L, MEMBER_ID))
                .willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> interestKeywordService.delete(MEMBER_ID, 15L))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INTEREST_KEYWORD_NOT_FOUND);
        then(interestKeywordRepository).should(never()).delete(any());
    }

    private DataIntegrityViolationException uniqueConstraintViolation() {
        return new DataIntegrityViolationException(
                "unique constraint violation",
                new ConstraintViolationException(
                        "unique constraint violation",
                        new SQLException(),
                        MemberInterestKeyword.UNIQUE_MEMBER_KEYWORD_CONSTRAINT));
    }
}
