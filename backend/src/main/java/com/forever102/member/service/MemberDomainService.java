package com.forever102.member.service;

import com.forever102.member.domain.Domain;
import com.forever102.member.dto.DomainResponse;
import com.forever102.member.repository.MemberDomainRepository;
import java.util.EnumSet;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MemberDomainService {

    private final MemberDomainRepository memberDomainRepository;

    /**
     * 본인이 선택한 관심 분야를 조회한다. 아직 고르지 않았으면 빈 목록이다.
     * 온보딩 완료 여부는 이 목록이 아니라 회원 정보의 onboardingCompleted로 판단한다.
     */
    public List<DomainResponse> getMyDomains(Long memberId) {
        List<Domain> domains = memberDomainRepository.findDomainsByMemberId(memberId);
        if (domains.isEmpty()) {
            return List.of();
        }

        // 전체 분야 목록과 같은 순서로 내려주기 위해 enum 선언 순서로 정렬한다.
        return EnumSet.copyOf(domains).stream()
                .map(DomainResponse::from)
                .toList();
    }
}
