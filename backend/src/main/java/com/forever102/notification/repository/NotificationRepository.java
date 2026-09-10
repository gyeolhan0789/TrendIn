package com.forever102.notification.repository;

import com.forever102.notification.domain.Notification;
import java.util.Collection;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface NotificationRepository extends JpaRepository<Notification, Long> {

    @EntityGraph(attributePaths = "trend")
    Page<Notification> findAllByMemberIdOrderByCreatedAtDescIdDesc(
            Long memberId, Pageable pageable);

    long countByMemberIdAndReadFalse(Long memberId);

    @Query("""
            select new com.forever102.notification.repository.TrendNotificationTarget(
                    interestKeyword, interestKeyword.member, trend, interestKeyword.keyword.name)
            from MemberInterestKeyword interestKeyword
            join Trend trend on trend.keyword.id = interestKeyword.keyword.id
            """)
    List<TrendNotificationTarget> findTrendNotificationTargets();

    @Query("select notification.dedupKey from Notification notification "
            + "where notification.dedupKey in :dedupKeys")
    List<String> findExistingDedupKeys(@Param("dedupKeys") Collection<String> dedupKeys);
}
