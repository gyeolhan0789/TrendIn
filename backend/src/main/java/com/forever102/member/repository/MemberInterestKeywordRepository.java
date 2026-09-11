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
}
