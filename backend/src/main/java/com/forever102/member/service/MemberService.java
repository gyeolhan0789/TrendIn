package com.forever102.member.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.dto.MemberInfoResponse;
import com.forever102.member.dto.MemberUpdateRequest;
import com.forever102.auth.repository.RefreshTokenRepository;
import com.forever102.member.repository.MemberInterestKeywordRepository;
import com.forever102.member.repository.MemberRepository;
import com.forever102.notification.repository.NotificationRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MemberService {

    private final MemberRepository memberRepository;
    private final MemberInterestKeywordRepository interestKeywordRepository;
    private final NotificationRepository notificationRepository;
    private final RefreshTokenRepository refreshTokenRepository;

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

    /**
     * 본인 계정을 탈퇴 처리하고 모든 기기의 세션을 끊는다.
     *
     * <p><b>지우는 순서가 중요하다.</b> {@code members}를 참조하는 여섯 표 가운데 넷은
     * ON DELETE CASCADE라 회원 행과 함께 사라지지만, {@code member_interest_keywords}와
     * {@code notifications}에는 그 설정이 없다. 회원을 먼저 지우면 DB가 외래키 위반으로
     * 막으므로 그 둘을 비우고 나서 회원을 지운다.
     *
     * <p>함께 사라지는 것 — 관심 분야, 저장한 트렌드, 알림 설정, 외부 로그인 연결(CASCADE).
     * 여기서 직접 지우는 것 — 관심 키워드, 개인 알림.
     * <b>남는 것</b> — 트렌드·콘텐츠·키워드처럼 여러 회원이 함께 보는 자료. 탈퇴한 회원이
     * 담았다는 이유로 지우면 남은 회원의 화면이 비어 버린다.
     *
     * <p>세션은 트랜잭션이 끝난 뒤가 아니라 여기서 끊는다. Redis는 이 트랜잭션에 들어 있지
     * 않아 롤백돼도 되돌아가지 않지만, 그 방향의 실패는 "지워진 세션"이라 다시 로그인하면
     * 그만이다. 반대로 두면 회원이 사라졌는데 토큰이 살아 있는 창이 생긴다.
     */
    @Transactional
    public void withdraw(Long memberId) {
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        interestKeywordRepository.deleteAllByMemberId(memberId);
        notificationRepository.deleteAllByMemberId(memberId);
        memberRepository.delete(member);

        refreshTokenRepository.deleteAll(memberId);
    }
}
