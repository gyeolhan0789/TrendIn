package com.forever102.member.repository;

import com.forever102.auth.domain.OAuthProvider;
import com.forever102.member.domain.MemberOAuthAccount;
import java.util.Optional;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MemberOAuthAccountRepository extends JpaRepository<MemberOAuthAccount, Long> {

    /**
     * 재로그인은 이 조회로 같은 회원을 찾는다. 회원까지 함께 읽어 추가 질의를 막는다.
     */
    @EntityGraph(attributePaths = "member")
    Optional<MemberOAuthAccount> findByProviderAndProviderUserId(
            OAuthProvider provider, String providerUserId);
}
