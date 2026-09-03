package com.forever102.backend.auth.service;

import com.forever102.backend.auth.dto.SignUpRequest;
import com.forever102.backend.auth.dto.SignUpResponse;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.member.domain.Member;
import com.forever102.backend.member.repository.MemberRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional
public class AuthService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;

    public SignUpResponse signUp(SignUpRequest request) {
        if (memberRepository.existsByEmailAndDeletedAtIsNull(request.email())) {
            throw new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }

        Member member = Member.create(
                request.email(),
                passwordEncoder.encode(request.password()),
                request.nickname()
        );

        return SignUpResponse.from(save(member));
    }

    private Member save(Member member) {
        try {
            return memberRepository.saveAndFlush(member);
        } catch (DataIntegrityViolationException e) {
            throw new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }
    }
}
