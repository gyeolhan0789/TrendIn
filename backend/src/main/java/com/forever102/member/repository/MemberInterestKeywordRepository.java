package com.forever102.member.repository;

import com.forever102.member.domain.MemberInterestKeyword;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MemberInterestKeywordRepository extends JpaRepository<MemberInterestKeyword, Long> {

    boolean existsByMemberIdAndKeywordId(Long memberId, Long keywordId);
}
