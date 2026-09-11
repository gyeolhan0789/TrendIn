package com.forever102.member.service;

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
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MemberDomainService {

    private final MemberDomainRepository memberDomainRepository;
    private final MemberInterestKeywordRepository interestKeywordRepository;
    private final MemberRepository memberRepository;

    /**
     * 본인이 선택한 관심 분야를 조회한다. 아직 고르지 않았으면 빈 목록이다.
     * 온보딩 완료 여부는 이 목록이 아니라 회원 정보의 onboardingCompleted로 판단한다.
     */
    public List<DomainResponse> getMyDomains(Long memberId) {
        return toSortedResponses(memberDomainRepository.findDomainsByMemberId(memberId));
    }

    /**
     * 관심 분야를 요청 목록으로 통째로 교체한다.
     * 빠진 분야에 속한 관심 키워드도 같은 트랜잭션에서 지우므로, 분야와 키워드가 어긋난 상태로 남지 않는다.
     * 최소 1개는 반드시 유지해야 하며, 최초로 성공하면 온보딩을 완료 처리한다.
     */
    @Transactional
    public List<DomainResponse> updateMyDomains(Long memberId, MemberDomainUpdateRequest request) {
        Set<Domain> domains = request.toDomains();
        if (domains.isEmpty()) {
            throw new BusinessException(ErrorCode.INTEREST_COUNT_INVALID);
        }

        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        // 빠진 분야의 키워드를 먼저 지운다. 분야 행이 남아 있는 동안 정리해야 참조가 꼬이지 않는다.
        interestKeywordRepository.deleteByMemberIdAndKeywordDomainNotIn(memberId, domains);
        memberDomainRepository.deleteByMemberIdAndDomainNotIn(memberId, domains);

        addMissingDomains(member, domains);
        member.completeOnboarding();

        return toSortedResponses(memberDomainRepository.findDomainsByMemberId(memberId));
    }

    /**
     * 이미 선택된 분야는 그대로 두고 새로 추가된 분야만 저장한다.
     * 전부 지우고 다시 넣지 않으므로 기존 선택의 created_at이 보존된다.
     */
    private void addMissingDomains(Member member, Set<Domain> domains) {
        List<Domain> existing = memberDomainRepository.findDomainsByMemberId(member.getId());
        domains.stream()
                .filter(domain -> !existing.contains(domain))
                .map(domain -> MemberDomain.register(member, domain))
                .forEach(memberDomainRepository::save);
    }

    /** 전체 분야 목록과 같은 순서로 내려주기 위해 enum 선언 순서로 정렬한다. */
    private List<DomainResponse> toSortedResponses(List<Domain> domains) {
        if (domains.isEmpty()) {
            return List.of();
        }
        return EnumSet.copyOf(domains).stream()
                .map(DomainResponse::from)
                .toList();
    }
}
