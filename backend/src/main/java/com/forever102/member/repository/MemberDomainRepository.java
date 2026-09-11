package com.forever102.member.repository;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.MemberDomain;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface MemberDomainRepository extends JpaRepository<MemberDomain, Long> {

    /**
     * 회원이 선택한 분야 코드만 꺼낸다. 표시명은 enum이 들고 있어 엔티티 전체를 읽을 필요가 없다.
     * 정렬은 전체 분야 목록과 순서를 맞추기 위해 서비스에서 enum 선언 순서로 처리한다.
     */
    @Query("select md.domain from MemberDomain md where md.member.id = :memberId")
    List<Domain> findDomainsByMemberId(Long memberId);
}
