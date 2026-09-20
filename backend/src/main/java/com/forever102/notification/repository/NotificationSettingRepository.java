package com.forever102.notification.repository;

import com.forever102.notification.domain.NotificationSetting;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface NotificationSettingRepository extends JpaRepository<NotificationSetting, Long> {

    @EntityGraph(attributePaths = "member")
    Optional<NotificationSetting> findByMemberId(Long memberId);

    List<NotificationSetting> findAllByMemberIdIn(Collection<Long> memberIds);
}
