package com.forever102.member.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.member.dto.InterestKeywordRegisterRequest;
import com.forever102.member.dto.InterestKeywordRegisterResponse;
import com.forever102.member.dto.RecommendedKeywordResponse;
import com.forever102.member.repository.MemberInterestKeywordRepository;
import com.forever102.member.repository.MemberRepository;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.repository.KeywordRepository;
import com.forever102.trend.repository.KeywordRelationRepository;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.hibernate.exception.ConstraintViolationException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional
public class MemberInterestKeywordService {

    private final MemberRepository memberRepository;
    private final KeywordRepository keywordRepository;
    private final MemberInterestKeywordRepository interestKeywordRepository;
    private final KeywordRelationRepository keywordRelationRepository;

    public InterestKeywordRegisterResponse register(Long memberId, InterestKeywordRegisterRequest request) {
        Long keywordId = request.keywordId();
        if (interestKeywordRepository.existsByMemberIdAndKeywordId(memberId, keywordId)) {
            throw new BusinessException(ErrorCode.INTEREST_KEYWORD_ALREADY_EXISTS);
        }

        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        Keyword keyword = keywordRepository.findById(keywordId)
                .orElseThrow(() -> new BusinessException(ErrorCode.KEYWORD_NOT_FOUND));

        return InterestKeywordRegisterResponse.from(save(MemberInterestKeyword.register(member, keyword)));
    }

    @Transactional(readOnly = true)
    public List<RecommendedKeywordResponse> getRecommendedKeywords(Long memberId) {
        return keywordRelationRepository.findRecommendedKeywords(memberId).stream()
                .map(RecommendedKeywordResponse::from)
                .toList();
    }

    private MemberInterestKeyword save(MemberInterestKeyword interestKeyword) {
        try {
            return interestKeywordRepository.saveAndFlush(interestKeyword);
        } catch (DataIntegrityViolationException e) {
            if (isInterestKeywordUniqueViolation(e)) {
                throw new BusinessException(ErrorCode.INTEREST_KEYWORD_ALREADY_EXISTS);
            }
            throw e;
        }
    }

    private boolean isInterestKeywordUniqueViolation(DataIntegrityViolationException exception) {
        Throwable cause = exception;
        while (cause != null) {
            if (cause instanceof ConstraintViolationException violation
                    && MemberInterestKeyword.UNIQUE_MEMBER_KEYWORD_CONSTRAINT
                    .equalsIgnoreCase(violation.getConstraintName())) {
                return true;
            }
            cause = cause.getCause();
        }
        return false;
    }
}
