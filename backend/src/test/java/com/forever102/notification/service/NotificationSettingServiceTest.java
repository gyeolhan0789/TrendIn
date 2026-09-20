package com.forever102.notification.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

import com.forever102.member.domain.Member;
import com.forever102.member.repository.MemberRepository;
import com.forever102.notification.domain.NotificationSetting;
import com.forever102.notification.dto.NotificationSettingResponse;
import com.forever102.notification.dto.NotificationSettingUpdateRequest;
import com.forever102.notification.repository.NotificationSettingRepository;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class NotificationSettingServiceTest {

    @Mock NotificationSettingRepository settingRepository;
    @Mock MemberRepository memberRepository;
    @InjectMocks NotificationSettingService service;

    @Test
    void createsDefaultSettingsWhenMissing() {
        Member member = Member.create("member@example.com", "password", "회원");
        NotificationSetting defaults = NotificationSetting.defaults(member);
        given(settingRepository.findByMemberId(1L)).willReturn(Optional.empty());
        given(memberRepository.findById(1L)).willReturn(Optional.of(member));
        given(settingRepository.save(org.mockito.ArgumentMatchers.any())).willReturn(defaults);

        NotificationSettingResponse response = service.getSettings(1L);

        assertThat(response).isEqualTo(new NotificationSettingResponse(true, true, true, true));
        verify(settingRepository).save(org.mockito.ArgumentMatchers.any());
    }

    @Test
    void updatesAllSettings() {
        Member member = Member.create("member@example.com", "password", "회원");
        NotificationSetting setting = NotificationSetting.defaults(member);
        given(settingRepository.findByMemberId(1L)).willReturn(Optional.of(setting));

        NotificationSettingResponse response = service.updateSettings(1L,
                new NotificationSettingUpdateRequest(false, true, false, true));

        assertThat(response).isEqualTo(new NotificationSettingResponse(false, true, false, true));
    }
}
