package com.forever102.member.repository;

import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.member.domain.Domain;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MemberInterestKeywordRepository extends JpaRepository<MemberInterestKeyword, Long> {

    boolean existsByMemberIdAndKeywordId(Long memberId, Long keywordId);

    @EntityGraph(attributePaths = "keyword")
    List<MemberInterestKeyword> findAllByMemberIdOrderByIdAsc(Long memberId);

    @EntityGraph(attributePaths = "keyword")
    List<MemberInterestKeyword> findAllByMemberIdAndKeywordDomainOrderByIdAsc(
            Long memberId, Domain domain);

    Optional<MemberInterestKeyword> findByIdAndMemberId(Long id, Long memberId);
}
