package com.forever102.auth.oauth;

/**
 * 제공자에서 읽어온 사용자 정보 중 회원 생성에 필요한 만큼만 담는다.
 *
 * @param providerUserId 제공자가 발급한 불변 식별자
 * @param email          회원 식별에 쓰는 이메일. 제공자가 주지 않으면 회원을 만들 수 없다.
 * @param nickname       표시명. 길이 제한과 공백 정리는 회원 생성 시점에 맞춘다.
 */
public record OAuthUserInfo(
        String providerUserId,
        String email,
        String nickname
) {
}
