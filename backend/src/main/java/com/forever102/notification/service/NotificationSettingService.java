package com.forever102.notification.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.repository.MemberRepository;
import com.forever102.notification.domain.NotificationSetting;
import com.forever102.notification.dto.NotificationSettingResponse;
import com.forever102.notification.dto.NotificationSettingUpdateRequest;
import com.forever102.notification.repository.NotificationSettingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional
public class NotificationSettingService {

    private final NotificationSettingRepository settingRepository;
    private final MemberRepository memberRepository;

    public NotificationSettingResponse getSettings(Long memberId) {
        return NotificationSettingResponse.from(findOrCreate(memberId));
    }

    public NotificationSettingResponse updateSettings(
            Long memberId, NotificationSettingUpdateRequest request) {
        NotificationSetting setting = findOrCreate(memberId);
        setting.update(request.keywordSurgeEnabled(), request.keywordDropEnabled(),
                request.newTrendEnabled(), request.trendTurningPointEnabled());
        return NotificationSettingResponse.from(setting);
    }

    private NotificationSetting findOrCreate(Long memberId) {
        return settingRepository.findByMemberId(memberId).orElseGet(() -> {
            Member member = memberRepository.findById(memberId)
                    .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
            return settingRepository.save(NotificationSetting.defaults(member));
        });
    }
}
