package com.forever102.member.repository;

import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.member.domain.Domain;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

public interface MemberInterestKeywordRepository extends JpaRepository<MemberInterestKeyword, Long> {

    boolean existsByMemberIdAndKeywordId(Long memberId, Long keywordId);

    @EntityGraph(attributePaths = "keyword")
    List<MemberInterestKeyword> findAllByMemberIdOrderByIdAsc(Long memberId);

    @EntityGraph(attributePaths = "keyword")
    List<MemberInterestKeyword> findAllByMemberIdAndKeywordDomainOrderByIdAsc(
            Long memberId, Domain domain);

    Optional<MemberInterestKeyword> findByIdAndMemberId(Long id, Long memberId);

    /**
     * 관심 분야에서 빠진 분야의 관심 키워드를 지운다.
     * 분야 교체와 같은 트랜잭션에서 실행되어 분야와 키워드가 어긋난 상태로 남지 않는다.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("delete from MemberInterestKeyword mik "
            + "where mik.member.id = :memberId and mik.keyword.domain not in :domains")
    void deleteByMemberIdAndKeywordDomainNotIn(Long memberId, Collection<Domain> domains);

    /**
     * 탈퇴할 회원의 관심 키워드를 모두 지운다.
     *
     * <p>이 표의 외래키에는 ON DELETE CASCADE가 없다. 회원 행을 먼저 지우면 DB가 외래키
     * 위반으로 막으므로, 탈퇴는 이 표를 직접 비우고 나서 회원을 지운다.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("delete from MemberInterestKeyword mik where mik.member.id = :memberId")
    void deleteAllByMemberId(Long memberId);
}
