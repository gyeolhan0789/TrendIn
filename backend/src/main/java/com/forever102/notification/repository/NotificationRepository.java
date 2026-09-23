package com.forever102.notification.repository;

import com.forever102.notification.domain.Notification;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.repository.query.Param;

public interface NotificationRepository extends JpaRepository<Notification, Long> {

    @EntityGraph(attributePaths = "trend")
    Page<Notification> findAllByMemberIdOrderByCreatedAtDescIdDesc(
            Long memberId, Pageable pageable);

    long countByMemberIdAndReadFalse(Long memberId);

    Optional<Notification> findByIdAndMemberId(Long id, Long memberId);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Notification notification set notification.read = true "
            + "where notification.member.id = :memberId and notification.read = false")
    int markAllAsReadByMemberId(@Param("memberId") Long memberId);

    /**
     * 탈퇴할 회원의 알림을 모두 지운다.
     *
     * <p>이 표의 외래키에는 ON DELETE CASCADE가 없다. 회원 행을 먼저 지우면 DB가 외래키
     * 위반으로 막으므로, 탈퇴는 이 표를 직접 비우고 나서 회원을 지운다.
     *
     * <p>알림은 개인에게만 보이는 자료라 남길 이유가 없다. 알림이 가리키는 트렌드는
     * 공유 자료이므로 그대로 둔다.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("delete from Notification notification where notification.member.id = :memberId")
    void deleteAllByMemberId(@Param("memberId") Long memberId);

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
