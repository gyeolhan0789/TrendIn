package com.forever102.member.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.member.domain.Domain;
import com.forever102.member.dto.InterestKeywordRegisterRequest;
import com.forever102.member.dto.InterestKeywordRegisterResponse;
import com.forever102.member.dto.InterestKeywordResponse;
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
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional
public class MemberInterestKeywordService {

    /*
     * 추천은 연관도 상위 몇 개만 준다. 화면이 그만큼만 보여 주기 때문이기도 하지만,
     * 상한이 없으면 질의가 열려 있다는 것이 더 큰 이유다 — 추천 후보는 내 관심 키워드에
     * 연결된 keyword_relations 전부이므로, 관심 키워드를 많이 등록한 회원일수록 수백~수천
     * 행을 만들어 전송한다. 그 값을 화면에서 잘라도 DB 비용과 전송량은 그대로다.
     *
     * 파라미터로 열지 않는 이유는 지금 이 값을 정하는 곳이 화면 하나뿐이기 때문이다.
     * 다른 화면이 다른 개수를 요구하면 그때 컨트롤러로 올린다.
     */
    private static final int RECOMMENDATION_LIMIT = 8;

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
        // 정렬은 질의가 이미 갖고 있다(연관도 내림차순, 같으면 키워드 id). Pageable 에
        // sort 를 같이 주면 JPQL 의 order by 와 겹쳐 SQL 이 어긋나므로 크기만 넘긴다.
        Pageable limit = PageRequest.of(0, RECOMMENDATION_LIMIT);
        return keywordRelationRepository.findRecommendedKeywords(memberId, limit).stream()
                .map(RecommendedKeywordResponse::from)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<InterestKeywordResponse> getInterestKeywords(Long memberId, Domain domain) {
        List<MemberInterestKeyword> interestKeywords = domain == null
                ? interestKeywordRepository.findAllByMemberIdOrderByIdAsc(memberId)
                : interestKeywordRepository.findAllByMemberIdAndKeywordDomainOrderByIdAsc(
                        memberId, domain);
        return interestKeywords.stream().map(InterestKeywordResponse::from).toList();
    }

    public void delete(Long memberId, Long interestKeywordId) {
        MemberInterestKeyword interestKeyword = interestKeywordRepository
                .findByIdAndMemberId(interestKeywordId, memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INTEREST_KEYWORD_NOT_FOUND));
        interestKeywordRepository.delete(interestKeyword);
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
