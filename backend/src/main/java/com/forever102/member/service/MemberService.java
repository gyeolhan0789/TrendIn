package com.forever102.member.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.dto.MemberInfoResponse;
import com.forever102.member.dto.MemberUpdateRequest;
import com.forever102.member.repository.MemberRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MemberService {

    private final MemberRepository memberRepository;

    /**
     * 액세스 토큰이 가리키는 본인의 회원 정보를 조회한다.
     * 토큰은 유효하지만 회원이 남아 있지 않으면 MEMBER_NOT_FOUND로 알린다.
     */
    public MemberInfoResponse getMyInfo(Long memberId) {
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        return MemberInfoResponse.from(member);
    }

    /**
     * 본인의 회원 정보를 수정한다. 현재 수정 가능한 필드는 닉네임뿐이다.
     * 닉네임은 표시용이고 식별은 이메일로 하므로 중복을 막지 않는다.
     */
    @Transactional
    public MemberInfoResponse updateMyInfo(Long memberId, MemberUpdateRequest request) {
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        member.updateNickname(request.nickname());

        return MemberInfoResponse.from(member);
    }
}
